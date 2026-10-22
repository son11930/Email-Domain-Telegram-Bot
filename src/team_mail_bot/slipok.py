"""Bounded, secret-safe client for SlipOK's slip verification API."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

API_ORIGIN = "https://api.slipok.com"
MAX_IMAGE_BYTES = 512_000
MAX_RESPONSE_BYTES = 65_536
REQUEST_TIMEOUT_SECONDS = 15


class SlipOKError(RuntimeError):
    """Safe error without upstream message, body, uploaded image, or credentials."""

    def __init__(self, message="Slip verification failed; do not credit automatically", *, code=None):
        super().__init__(message)
        self.code = code


class SlipOKClient:
    def __init__(self, api_key: str, branch_id: str, *, client: httpx.Client | None = None):
        if (not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 512
                or any(ord(char) < 32 or ord(char) == 127 for char in api_key)):
            raise ValueError("Invalid SlipOK API key")
        if not isinstance(branch_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", branch_id):
            raise ValueError("Invalid SlipOK branch ID")
        self._api_key = api_key
        self._branch_id = branch_id
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False)

    def close(self):
        if self._owns_client:
            self._client.close()

    def verify_slip(self, image: bytes, filename: str, expected_amount: Decimal) -> dict:
        mime_type = _validate_image(image, filename)
        amount = _amount(expected_amount)
        url = f"{API_ORIGIN}/api/line/apikey/{quote(self._branch_id, safe='')}"
        files = {"files": (filename, image, mime_type)}
        data = {"amount": format(amount, "f"), "log": "true"}
        try:
            with self._client.stream(
                "POST", url, headers={"x-authorization": self._api_key},
                files=files, data=data, timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as response:
                body_bytes = _read_limited(response)
                status = response.status_code
        except httpx.HTTPError:
            raise SlipOKError("Slip verification service is unavailable; do not credit automatically") from None
        try:
            body = json.loads(body_bytes, parse_float=Decimal)
        except (ValueError, UnicodeDecodeError):
            raise SlipOKError("Slip verification service returned invalid data") from None
        if status != 200:
            code = body.get("code") if isinstance(body, dict) else None
            if type(code) is not int:
                code = None
            raise SlipOKError(_error_message(code), code=code)
        if not isinstance(body, dict) or body.get("success") is not True:
            raise SlipOKError("Slip verification service did not confirm the slip")
        result = body.get("data")
        if not isinstance(result, dict) or result.get("success") is not True:
            raise SlipOKError("Slip verification service did not confirm the slip")
        return _normalize(result)


def _validate_image(image: bytes, filename: str) -> str:
    if not isinstance(image, bytes) or not 12 <= len(image) <= MAX_IMAGE_BYTES:
        raise ValueError("Slip image size is invalid")
    if (not isinstance(filename, str) or len(filename) > 100 or filename.startswith(".")
            or ".." in filename or "/" in filename or "\\" in filename
            or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", filename)):
        raise ValueError("Slip image filename is invalid")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type, supported = "image/png", {"png"}
    elif image.startswith(b"\xff\xd8\xff"):
        mime_type, supported = "image/jpeg", {"jpg", "jpeg", "jfif"}
    elif image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        mime_type, supported = "image/webp", {"webp"}
    else:
        raise ValueError("Slip image type is not supported")
    if extension not in supported:
        raise ValueError("Slip image extension does not match its content")
    return mime_type


def _amount(value: Decimal) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("Slip amount is invalid")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        raise ValueError("Slip amount is invalid") from None
    return amount


def _read_limited(response: httpx.Response) -> bytes:
    raw_length = response.headers.get("content-length")
    if raw_length:
        try:
            if int(raw_length) > MAX_RESPONSE_BYTES:
                raise SlipOKError("Slip verification service response is too large")
        except ValueError:
            raise SlipOKError("Slip verification service response is invalid") from None
    chunks = []
    total = 0
    try:
        for chunk in response.iter_bytes(chunk_size=8192):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise SlipOKError("Slip verification service response is too large")
            chunks.append(chunk)
    except httpx.HTTPError:
        raise SlipOKError("Slip verification service returned invalid data") from None
    return b"".join(chunks)


def _normalize(data: dict) -> dict:
    trans_ref = data.get("transRef")
    if not isinstance(trans_ref, str) or not trans_ref.strip() or len(trans_ref) > 256:
        raise SlipOKError("Slip transaction reference is missing or invalid")
    try:
        amount = _amount(data.get("amount"))
    except ValueError:
        raise SlipOKError("Slip amount is missing or invalid") from None
    timestamp = data.get("transTimestamp")
    if not isinstance(timestamp, str):
        raise SlipOKError("Slip transaction time is missing or invalid")
    try:
        occurred_at = datetime.fromisoformat(timestamp)
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError()
        occurred_at = occurred_at.astimezone(UTC)
    except (ValueError, OverflowError):
        raise SlipOKError("Slip transaction time is missing or invalid") from None
    country_code = data.get("countryCode")
    if country_code != "TH" or data.get("paidLocalCurrency") != "764":
        raise SlipOKError("Slip currency or country is missing or invalid")
    receiver = data.get("receiver")
    if not isinstance(receiver, dict):
        raise SlipOKError("Slip recipient is missing or invalid")
    receiver_name = receiver.get("displayName") or receiver.get("name")
    account = receiver.get("account")
    if (not isinstance(receiver_name, str) or not receiver_name.strip()
            or not isinstance(account, dict) or not isinstance(account.get("value"), str)
            or not account["value"].strip()):
        raise SlipOKError("Slip recipient is missing or invalid")
    return {
        "trans_ref": trans_ref.strip(),
        "amount": amount,
        "occurred_at": occurred_at,
        "country_code": country_code,
        "receiver_name": receiver_name.strip(),
        "receiver_account": account["value"].strip(),
        "receiver_account_type": account.get("type", ""),
    }


def _error_message(code: int | None) -> str:
    messages = {
        1010: "Slip is delayed by the bank; do not credit yet",
        1012: "Slip was already used; do not credit again",
        1013: "Slip amount does not match the requested amount",
        1014: "Slip recipient does not match the registered account",
    }
    return messages.get(code, "Slip verification failed; do not credit automatically")
