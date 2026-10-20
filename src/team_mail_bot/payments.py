"""Read-only Binance Pay history and restart-safe reconciliation.

Never log requests: their query strings contain an HMAC signature. History is
complete or raises; a saturated millisecond cannot be paginated by this API.
"""
import hashlib
import hmac
import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode, urlsplit

import httpx

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DAY_MS = 86_400_000
UNITS = 100_000_000


class PaymentError(RuntimeError):
    """Safe, actionable error without upstream content or signed URLs."""


def _milliseconds(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Payment times must include a timezone")
    delta = value.astimezone(UTC) - EPOCH
    result = delta.days * DAY_MS + delta.seconds * 1000 + delta.microseconds // 1000
    if result < 0:
        raise ValueError("Payment times must be after the Unix epoch")
    return result


class BinancePayClient:
    def __init__(self, api_key, api_secret, receiver_id, *,
                 base_url="https://api.binance.com", client=None):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Binance base URL must use HTTPS without credentials")
        if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("Invalid Binance base URL")
        if not all(isinstance(value, str) and value.strip() for value in (api_key, api_secret, receiver_id)):
            raise ValueError("Binance credentials and receiver ID are required")
        self._api_key = api_key
        self._api_secret = api_secret.encode()
        self.receiver_id = receiver_id
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=20, follow_redirects=False)

    def close(self):
        if self._owns_client:
            self._client.close()

    def _fetch(self, start_ms, end_ms):
        params = [("startTime", start_ms), ("endTime", end_ms), ("limit", 100),
                  ("recvWindow", 5000), ("timestamp", time.time_ns() // 1_000_000)]
        query = urlencode(params)
        signature = hmac.new(self._api_secret, query.encode(), hashlib.sha256).hexdigest()
        try:
            response = self._client.get(
                self._base_url + "/sapi/v1/pay/transactions?" + query + "&signature=" + signature,
                headers={"X-MBX-APIKEY": self._api_key}, follow_redirects=False, timeout=20)
        except httpx.HTTPError:
            raise PaymentError("Binance Pay connection failed; retry later") from None
        if response.status_code != 200:
            raise PaymentError("Binance Pay HTTP request failed; check connectivity or API permissions")
        try:
            body = response.json()
        except ValueError:
            raise PaymentError("Binance Pay returned invalid JSON") from None
        if (not isinstance(body, dict) or body.get("success") is not True
                or body.get("code") != "000000" or not isinstance(body.get("data"), list)):
            raise PaymentError("Binance Pay rejected history request or returned an invalid response")
        if len(body["data"]) > 100:
            raise PaymentError("Binance Pay returned an unexpected page size")
        return body["data"]

    def history(self, start: datetime, end: datetime) -> list[dict]:
        start_ms, end_ms = _milliseconds(start), _milliseconds(end)
        if end_ms < start_ms:
            raise ValueError("Payment history end precedes start")
        pending = [(start_ms, end_ms)]
        found = {}
        requests = 0
        while pending:
            lower, upper = pending.pop()
            if upper - lower >= 90 * DAY_MS:
                midpoint = (lower + upper) // 2
                pending.extend([(midpoint + 1, upper), (lower, midpoint)])
                continue
            requests += 1
            if requests > 2048:
                raise PaymentError("Cannot retrieve complete history within request budget")
            rows = self._fetch(lower, upper)
            if len(rows) == 100:
                if lower == upper:
                    raise PaymentError("Cannot retrieve complete history: saturated millisecond")
                midpoint = (lower + upper) // 2
                pending.extend([(midpoint + 1, upper), (lower, midpoint)])
                continue
            for row in rows:
                normalized = self._normalize(row, lower, upper)
                if normalized is not None:
                    key = normalized["transaction_id"]
                    if key in found and found[key] != normalized:
                        raise PaymentError("Binance Pay returned conflicting transaction records")
                    found = {**found, key: normalized}
        return sorted(found.values(), key=lambda row: (row["occurred_at"], row["transaction_id"]))

    def _normalize(self, row, lower, upper):
        if not isinstance(row, dict):
            raise PaymentError("Binance Pay returned malformed transaction data")
        if row.get("currency") != "USDT" or row.get("orderType") not in ("C2C", "PAY"):
            return None
        raw_amount = row.get("amount")
        if not isinstance(raw_amount, str) or not re.fullmatch(r"-?\d{1,12}(?:\.\d{1,8})?", raw_amount):
            raise PaymentError("Binance Pay returned an invalid amount")
        amount_units = int(Decimal(raw_amount) * UNITS)
        if amount_units < 0:
            return None
        if amount_units == 0:
            raise PaymentError("Binance Pay returned a zero income amount")
        receiver, payer = row.get("receiverInfo"), row.get("payerInfo", {})
        if not isinstance(receiver, dict) or not any(receiver.get(k) for k in ("binanceId", "accountId")):
            raise PaymentError("Binance Pay income receiver could not be verified")
        if self.receiver_id not in (str(receiver.get("binanceId", "")), str(receiver.get("accountId", ""))):
            return None
        if not isinstance(payer, dict):
            raise PaymentError("Binance Pay returned invalid payer data")
        if str(payer.get("binanceId", "")) == self.receiver_id:
            return None  # Self/sender record; a foreign payer ID is legitimate.
        transaction_id, occurred_ms = row.get("transactionId"), row.get("transactionTime")
        if not isinstance(transaction_id, str) or not transaction_id or len(transaction_id) > 256:
            raise PaymentError("Binance Pay returned an invalid transaction identity")
        if type(occurred_ms) is not int or not lower <= occurred_ms <= upper:
            raise PaymentError("Binance Pay returned an invalid transaction time")
        try:
            occurred_at = EPOCH + timedelta(milliseconds=occurred_ms)
        except OverflowError:
            raise PaymentError("Binance Pay returned an invalid transaction time") from None
        return {"transaction_id": transaction_id, "amount_units": amount_units,
                "currency": "USDT", "occurred_at": occurred_at,
                "receiver_id": self.receiver_id, "order_type": row["orderType"]}


class PaymentPoller:
    def __init__(self, client, service, *, lookback_seconds=86400, overlap_seconds=300):
        if lookback_seconds <= 0 or overlap_seconds < 0 or overlap_seconds > lookback_seconds:
            raise ValueError("Invalid payment reconciliation interval")
        self.client = client
        self.service = service
        self.lookback_seconds = lookback_seconds
        self.overlap_seconds = overlap_seconds

    def poll_once(self, now=None) -> int:
        current = now or datetime.now(UTC)
        _milliseconds(current)
        current = current.astimezone(UTC)
        checkpoint = self.service.get_checkpoint("binance_pay")
        start = current - timedelta(seconds=self.lookback_seconds)
        if checkpoint is not None:
            _milliseconds(checkpoint)
            start = min(start, checkpoint.astimezone(UTC) - timedelta(seconds=self.overlap_seconds))
        # Reconcile the bounded recent history on every run, so delayed indexing
        # behind an advanced checkpoint is still seen. Database references dedup.
        records = self.client.history(start, current)
        for payment in records:
            self.service.record_payment(**payment)
        self.service.set_checkpoint("binance_pay", current)
        return len(records)
