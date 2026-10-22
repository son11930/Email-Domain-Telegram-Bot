from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from team_mail_bot.slipok import SlipOKClient, SlipOKError

PNG = b"\x89PNG\r\n\x1a\n" + b"payload"


def response_data(**overrides):
    data = {
        "success": True,
        "transRef": "bank-ref-123",
        "transTimestamp": "2026-10-23T02:00:00.000Z",
        "amount": 150.37,
        "countryCode": "TH",
        "paidLocalCurrency": "764",
        "receiver": {
            "displayName": "ชื่อบัญชี",
            "name": "ACCOUNT NAME",
            "account": {"type": "BANKAC", "value": "xxx-x-x539-x"},
        },
    }
    data.update(overrides)
    return {"success": True, "data": data}


def make_client(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return SlipOKClient("test-api-key", "branch_123", client=http)


def test_posts_image_with_credentials_expected_amount_and_duplicate_check():
    def handler(request):
        assert request.method == "POST"
        assert request.url == "https://api.slipok.com/api/line/apikey/branch_123"
        assert request.headers["x-authorization"] == "test-api-key"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        body = request.read()
        assert b'name="files"; filename="slip.png"' in body
        assert b"image/png" in body
        assert b'name="amount"\r\n\r\n150.37' in body
        assert b'name="log"\r\n\r\ntrue' in body
        return httpx.Response(200, json=response_data())

    result = make_client(handler).verify_slip(PNG, "slip.png", Decimal("150.37"))
    assert result == {
        "trans_ref": "bank-ref-123",
        "amount": Decimal("150.37"),
        "occurred_at": datetime(2026, 10, 23, 2, 0, tzinfo=UTC),
        "country_code": "TH",
        "receiver_name": "ชื่อบัญชี",
        "receiver_account": "xxx-x-x539-x",
        "receiver_account_type": "BANKAC",
    }


@pytest.mark.parametrize(("filename", "content"), [
    ("wrong.jpg", PNG),
    ("../slip.png", PNG),
    ("C:\\temp\\slip.png", PNG),
    ("slip.exe", PNG),
    ("slip.png", b"not an image"),
    ("slip.png", b"\xff\xd8\xff"),
])
def test_rejects_filename_tricks_and_invalid_image_content(filename, content):
    client = make_client(lambda request: pytest.fail("must reject before HTTP request"))
    with pytest.raises(ValueError):
        client.verify_slip(content, filename, Decimal("150.37"))


def test_rejects_oversized_upload_before_http_request():
    client = make_client(lambda request: pytest.fail("must reject before HTTP request"))
    with pytest.raises(ValueError, match="size"):
        client.verify_slip(b"\x89PNG\r\n\x1a\n" + b"x" * 512_000,
                           "slip.png", Decimal("150.37"))


@pytest.mark.parametrize(("status", "body", "code"), [
    (400, {"code": 1012, "message": "duplicate with secret"}, 1012),
    (400, {"code": 1013, "message": "wrong amount"}, 1013),
    (400, {"code": 1014, "message": "wrong receiver"}, 1014),
    (401, {"code": 1002, "message": "private response"}, 1002),
])
def test_rejects_api_failures_without_leaking_upstream_message(status, body, code):
    client = make_client(lambda request: httpx.Response(status, json=body))
    with pytest.raises(SlipOKError) as error:
        client.verify_slip(PNG, "slip.png", Decimal("150.37"))
    assert error.value.code == code
    assert "secret" not in str(error.value)
    assert "private" not in str(error.value)
    assert "wrong receiver" not in str(error.value)


@pytest.mark.parametrize("body", [
    {"success": False, "message": "private"},
    {"success": True, "data": {"success": False, "message": "private"}},
    {"success": True, "data": []},
    {"success": True, "data": None},
])
def test_rejects_non_success_api_shapes(body):
    client = make_client(lambda request: httpx.Response(200, json=body))
    with pytest.raises(SlipOKError):
        client.verify_slip(PNG, "slip.png", Decimal("150.37"))


@pytest.mark.parametrize(("changes", "field"), [
    ({"transRef": ""}, "transaction reference"),
    ({"transTimestamp": "bad"}, "transaction time"),
    ({"transTimestamp": "2026-10-23T02:00:00"}, "transaction time"),
    ({"amount": "NaN"}, "amount"),
    ({"amount": 150.375}, "amount"),
    ({"countryCode": "US"}, "country"),
    ({"receiver": None}, "recipient"),
    ({"receiver": {"displayName": "Name", "account": {"value": ""}}}, "recipient"),
])
def test_rejects_missing_or_invalid_required_fields(changes, field):
    client = make_client(lambda request: httpx.Response(200, json=response_data(**changes)))
    with pytest.raises(SlipOKError, match=field):
        client.verify_slip(PNG, "slip.png", Decimal("150.37"))


def test_rejects_invalid_expected_amount_before_http_request():
    client = make_client(lambda request: pytest.fail("must reject before HTTP request"))
    for amount in (Decimal(0), Decimal("NaN"), Decimal("1.001")):
        with pytest.raises(ValueError):
            client.verify_slip(PNG, "slip.png", amount)


def test_validate_image_checks_locally_without_calling_slipok():
    client = make_client(lambda request: pytest.fail("validation must be local"))
    assert client.validate_image(PNG, 'slip.png') == 'image/png'
    with pytest.raises(ValueError, match='type'):
        client.validate_image(b'not an image', 'slip.png')


def test_timeout_is_safe_and_does_not_expose_credentials_or_image():
    def handler(request):
        raise httpx.ReadTimeout("test-api-key and image bytes", request=request)

    client = make_client(handler)
    with pytest.raises(SlipOKError) as error:
        client.verify_slip(PNG, "slip.png", Decimal("150.37"))
    assert "test-api-key" not in str(error.value)
    assert "image bytes" not in str(error.value)


def test_rejects_redirects_and_oversized_or_malformed_responses():
    for response in (
        httpx.Response(302, headers={"Location": "https://attacker.example"}),
        httpx.Response(200, content=b"{"),
        httpx.Response(200, content=b"x" * 65_537),
    ):
        client = make_client(lambda request, response=response: response)
        with pytest.raises(SlipOKError):
            client.verify_slip(PNG, "slip.png", Decimal("150.37"))


@pytest.mark.parametrize(("api_key", "branch_id"), [
    ("", "branch"), ("secret\r\nInjected: true", "branch"),
    ("key", "../branch"), ("key", "https://attacker.example/path"),
])
def test_rejects_invalid_credentials_and_branch_id(api_key, branch_id):
    with pytest.raises(ValueError):
        SlipOKClient(api_key, branch_id, client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=response_data()))))
