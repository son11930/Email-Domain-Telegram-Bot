import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest

from team_mail_bot.payments import BinancePayClient, PaymentError, PaymentPoller

NOW = datetime(2026, 10, 20, tzinfo=UTC)
MS = int(NOW.timestamp() * 1000)


def record(**changes):
    return {"transactionId": "tx1", "transactionTime": MS, "amount": "1.0037",
            "currency": "USDT", "orderType": "C2C", "receiverInfo": {"binanceId": "123"},
            "payerInfo": {"name": "sender"}, **changes}


def api(handler):
    return BinancePayClient("public-key", "private-secret", "123",
                            client=httpx.Client(transport=httpx.MockTransport(handler)))


def ok(rows):
    return httpx.Response(200, json={"success": True, "code": "000000", "data": rows})


def test_exact_signature_and_normalized_amount():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/sapi/v1/pay/transactions"
        assert request.headers["X-MBX-APIKEY"] == "public-key"
        unsigned, signature = request.url.query.decode().rsplit("&signature=", 1)
        assert signature == hmac.new(b"private-secret", unsigned.encode(), hashlib.sha256).hexdigest()
        query = parse_qs(unsigned)
        assert query["recvWindow"] == ["5000"]
        assert query["limit"] == ["100"]
        return ok([record()])
    result = api(handler).history(NOW, NOW)
    assert result == [{"transaction_id": "tx1", "amount_units": 100370000,
                       "currency": "USDT", "occurred_at": NOW, "receiver_id": "123", "order_type": "C2C"}]


@pytest.mark.parametrize("changes", [
    {"amount": "-1"}, {"currency": "BNB"}, {"orderType": "PAY_REFUND"},
    {"orderType": "CRYPTO_BOX"}, {"receiverInfo": {"binanceId": "other"}},
    {"payerInfo": {"binanceId": "123"}},
])
def test_rejects_outgoing_wrong_receiver_and_unaccepted_types(changes):
    assert api(lambda r: ok([record(**changes)])).history(NOW, NOW) == []


def test_pay_id_matching_supported():
    result = api(lambda r: ok([record(receiverInfo={"accountId": "123"}, orderType="PAY")])).history(NOW, NOW)
    assert result[0]["amount_units"] == 100370000


def test_positive_matching_receiver_accepts_foreign_payer_id():
    # Binance's official sample exposes both IDs even though incoming records
    # commonly contain only the payer name. Positive amount confirms income.
    result = api(lambda r: ok([record(payerInfo={"binanceId": "456", "name": "Jack"},
                                     receiverInfo={"binanceId": "123", "name": "Alan"})])).history(NOW, NOW)
    assert result[0]["transaction_id"] == "tx1"
    assert result[0]["amount_units"] == 100370000


@pytest.mark.parametrize("changes", [
    {"amount": "NaN"}, {"amount": "Infinity"}, {"amount": "1.000000001"},
    {"amount": 1.0037}, {"amount": "1e3"}, {"receiverInfo": {}},
    {"transactionTime": "bad"}, {"transactionId": ""}, {"amount": "0"},
])
def test_malformed_incoming_fails_safely(changes):
    with pytest.raises(PaymentError):
        api(lambda r: ok([record(**changes)])).history(NOW, NOW)


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={"success": False, "code": "000000", "data": []}),
    httpx.Response(200, json={"success": True, "code": "-1", "message": "secret", "data": []}),
    httpx.Response(200, json={"success": True, "code": "000000", "data": {}}),
    httpx.Response(429, text="private-secret"), httpx.Response(200, text="private-secret"),
])
def test_api_errors_are_safe(response):
    with pytest.raises(PaymentError) as error:
        api(lambda r: response).history(NOW, NOW)
    assert "secret" not in str(error.value)


def test_transport_error_is_redacted():
    def broken(request):
        raise httpx.ReadTimeout("secret query", request=request)
    with pytest.raises(PaymentError) as error:
        api(broken).history(NOW, NOW)
    assert "secret" not in str(error.value)


def test_full_pages_split_with_inclusive_nonoverlap_boundaries():
    windows = []
    def handler(request):
        query = parse_qs(request.url.query.decode())
        start, end = int(query["startTime"][0]), int(query["endTime"][0])
        windows.append((start, end))
        if end > start:
            return ok([record(transactionId=f"full{i}") for i in range(100)])
        return ok([record(transactionId=f"tx{start}", transactionTime=start)])
    result = api(handler).history(NOW, NOW + timedelta(milliseconds=3))
    assert len(result) == 4
    assert windows == [(MS, MS+3), (MS, MS+1), (MS, MS), (MS+1, MS+1),
                       (MS+2, MS+3), (MS+2, MS+2), (MS+3, MS+3)]


def test_full_single_millisecond_fails_instead_of_truncating():
    with pytest.raises(PaymentError, match="complete"):
        api(lambda r: ok([record(transactionId=str(i)) for i in range(100)])).history(NOW, NOW)


def test_conflicting_duplicate_and_out_of_range_time_fail():
    with pytest.raises(PaymentError):
        api(lambda r: ok([record(), record(amount="2")])).history(NOW, NOW)
    with pytest.raises(PaymentError):
        api(lambda r: ok([record(transactionTime=MS+1)])).history(NOW, NOW)


class Service:
    def __init__(self):
        self.checkpoint = NOW - timedelta(minutes=5)
        self.records = []
    def get_checkpoint(self, key):
        assert key == "binance_pay"
        return self.checkpoint
    def set_checkpoint(self, key, value):
        self.checkpoint = value
    def record_payment(self, **kwargs):
        self.records.append(kwargs)


def test_poller_reconciles_lookback_and_saves_checkpoint_last():
    service = Service()
    class Reader:
        def history(self, start, end):
            assert start == NOW - timedelta(days=1)
            assert end == NOW
            return [{"transaction_id": "late"}]
    assert PaymentPoller(Reader(), service).poll_once(NOW) == 1
    assert service.records == [{"transaction_id": "late"}]
    assert service.checkpoint == NOW


def test_poller_failure_keeps_checkpoint():
    service = Service()
    previous = service.checkpoint
    class Reader:
        def history(self, start, end):
            raise PaymentError("Unavailable")
    with pytest.raises(PaymentError):
        PaymentPoller(Reader(), service).poll_once(NOW)
    assert service.checkpoint == previous


def test_poller_record_failure_keeps_checkpoint():
    service = Service()
    previous = service.checkpoint
    def broken(**kwargs):
        raise RuntimeError("db unavailable")
    service.record_payment = broken
    class Reader:
        def history(self, start, end):
            return [{"transaction_id": "tx"}]
    with pytest.raises(RuntimeError):
        PaymentPoller(Reader(), service).poll_once(NOW)
    assert service.checkpoint == previous


def test_naive_or_reversed_intervals_rejected():
    client = api(lambda r: ok([]))
    with pytest.raises(ValueError):
        client.history(NOW.replace(tzinfo=None), NOW)
    with pytest.raises(ValueError):
        client.history(NOW, NOW - timedelta(seconds=1))


def test_large_paged_history_deduplicates_and_preserves_chronological_order():
    records = [record(transactionId=f'tx{index:04}', transactionTime=MS + index) for index in range(350)]

    def handler(request):
        query = parse_qs(request.url.query.decode())
        lower, upper = int(query['startTime'][0]), int(query['endTime'][0])
        rows = list(reversed([row for row in records if lower <= row['transactionTime'] <= upper]))
        if len(rows) >= 99:
            return ok(rows[:100])
        return ok(rows + rows[:1])

    result = api(handler).history(NOW, NOW + timedelta(milliseconds=349))
    assert [row['transaction_id'] for row in result] == [f'tx{index:04}' for index in range(350)]
