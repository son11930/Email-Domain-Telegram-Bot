import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from team_mail_bot.workers import DiscordNotifier, OutboxWorker, split_email_lines


def test_split_preserves_every_email_and_limit():
    emails = [f'user{n}@sub.example.org' for n in range(700)]
    parts = split_email_lines(emails)
    assert all(len(part) <= 4000 for part in parts)
    assert '\n'.join(parts).splitlines() == emails


def test_split_rejects_oversized_email():
    with pytest.raises(ValueError):
        split_email_lines(['a' * 5000])


def test_discord_contains_no_mentions_or_email_inventory():
    sent = []
    def respond(request):
        import json
        payload = json.loads(request.content)
        sent.append(payload['content'])
        assert payload['allowed_mentions'] == {'parse': []}
        assert 'stolen@example.org' not in str(payload)
        assert request.url.params['wait'] == 'true'
        return httpx.Response(200, json={'id': '123'})
    client = httpx.Client(transport=httpx.MockTransport(respond))
    notifier = DiscordNotifier('https://discord.com/api/webhooks/1/token', 'https://discord.com/api/webhooks/2/token', client=client)
    notifier.send('discord_order', {'order_id': 'abc', 'user_id': 42, 'user_name': 'Team\n@everyone',
        'quantity': 1, 'total_units': 30000000, 'balance_units': 20000000,
        'status': 'success', 'emails': ['stolen@example.org']})
    assert 'Team @everyone (ID 42)' in sent[0]
    assert 'pending' not in sent[0]
    assert 'สำเร็จ' in sent[0]
    notifier.send('discord_topup', {'topup_id': 'topup', 'user_id': 42,
        'user_name': 'Team\nMember', 'amount_units': 100000000, 'balance_units': 120000000})
    assert 'Team Member (ID 42)' in sent[1]


def test_discord_order_failure_message_is_explicit():
    sent = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: (
        sent.append(request.content.decode()) or httpx.Response(200))))
    notifier = DiscordNotifier('https://discord.com/api/webhooks/1/token',
        'https://discord.com/api/webhooks/2/token', client=client)
    notifier.send('discord_order', {'order_id': 'abc', 'user_id': 42, 'user_name': 'Team',
        'quantity': 1, 'total_units': 30000000, 'balance_units': 100000000,
        'status': 'refunded', 'failure_reason': 'returned'})
    assert 'ยกเลิก / คืนเครดิต' in sent[0]
    assert 'รายละเอียด: returned' in sent[0]


def test_discord_rate_limit_uses_retry_after_and_safe_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, json={'retry_after': 17})))
    notifier = DiscordNotifier('https://discord.com/api/webhooks/1/token', 'https://discord.com/api/webhooks/2/token', client=client)
    with pytest.raises(Exception) as exc:
        notifier.send('discord_topup', {})
    assert exc.value.retry_seconds == 17
    assert 'token' not in str(exc.value)


class FakeService:
    def __init__(self, jobs):
        self.jobs, self.enqueued, self.finished = jobs, [], []
    def claim_outbox(self, limit=20):
        return self.jobs
    def get_order(self, user_id, order_id):
        return {'id': order_id, 'user_id': user_id, 'emails': ['a@example.org', 'b@example.org'],
                'quantity': 2, 'total_units': 60000000, 'balance_units': 40000000,
                'status': 'delivered'}
    def enqueue(self, topic, payload, dedupe_key):
        self.enqueued.append((topic, payload, dedupe_key))
    def finish_outbox(self, job_id, success, error='', retry_seconds=30, lease_token=None,
                      permanent_failure=False, delivery_kind='', email_count=None,
                      refund_eligible=None):
        self.finished.append((job_id, success, error, retry_seconds, permanent_failure,
                              delivery_kind, email_count, refund_eligible))
    def mark_order_delivered(self, order_id):
        pass


def test_order_expands_one_file_and_all_text_idempotent_keys():
    service = FakeService([{'id': 1, 'topic': 'telegram_order', 'payload': {'order_id': 'o', 'user_id': 42}, 'attempts': 1}])
    worker = OutboxWorker(service, SimpleNamespace(), SimpleNamespace())
    asyncio.run(worker.run_once())
    assert [topic for topic, _, _ in service.enqueued].count('telegram_document') == 1
    messages = [payload['text'] for topic, payload, _ in service.enqueued if topic == 'telegram_text']
    assert 'a@example.org\nb@example.org' in messages
    email_part = next(payload for topic, payload, _ in service.enqueued
                      if topic == 'telegram_text' and payload.get('delivery_kind') == 'email')
    assert email_part['email_count'] == 2
    assert any(payload.get('delivery_kind') == 'summary'
               for topic, payload, _ in service.enqueued if topic == 'telegram_text')
    assert service.finished[0][1] is True


def test_resend_expansion_marks_all_email_parts_non_refundable():
    service = FakeService([{'id': 12, 'topic': 'telegram_order', 'dedupe_key': 'resend:o:key',
        'payload': {'order_id': 'o', 'user_id': 42, 'delivery_mode': 'resend',
                    'refund_eligible': False}, 'attempts': 1}])
    worker = OutboxWorker(service, SimpleNamespace(), SimpleNamespace())
    asyncio.run(worker.run_once())
    email_parts = [payload for topic, payload, _ in service.enqueued
                   if topic == 'telegram_text' and payload.get('delivery_kind') == 'email']
    assert email_parts
    assert all(part['refund_eligible'] is False for part in email_parts)


def test_transport_error_retries_same_part_without_purchase():
    from unittest.mock import Mock

    service = FakeService([{'id': 3, 'topic': 'telegram_text', 'payload': {'user_id': 42, 'text': 'a@example.org', 'order_id': 'o'}, 'attempts': 1}])
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError('sensitive transport data')))
    discord = Mock()
    asyncio.run(OutboxWorker(service, bot, discord).run_once())
    assert service.finished[0][1] is False
    assert 'sensitive' not in service.finished[0][2]
    assert service.finished[0][4] is False
    discord.send.assert_not_called()


def test_permanent_telegram_rejection_marks_failure_as_terminal():
    from unittest.mock import Mock

    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    service = FakeService([{'id': 9, 'topic': 'telegram_text', 'payload': {
        'user_id': 42, 'order_id': 'o', 'text': 'a@example.org\nb@example.org'},
        'attempts': 1, 'lease_token': 'lease'}])
    bad_request = TelegramBadRequest(method=SendMessage(chat_id=42, text='x'), message='chat not found')
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=bad_request))
    asyncio.run(OutboxWorker(service, bot, Mock()).run_once())
    assert service.finished[0][1] is False
    assert service.finished[0][2] == 'TelegramBadRequest'
    assert service.finished[0][4] is True
    assert service.finished[0][5:] == ('email', 2, None)


def test_delivery_failure_notice_reports_refund_without_email_content():
    service = FakeService([{'id': 10, 'topic': 'telegram_delivery_failure', 'payload': {
        'user_id': 42, 'order_id': 'o', 'failed_emails': 2,
        'refund_units': 60_000_000, 'refund_applied': True,
        'balance_units': 120_000_000}, 'attempts': 1}])
    bot = SimpleNamespace(send_message=AsyncMock())
    asyncio.run(OutboxWorker(service, bot, SimpleNamespace()).run_once())
    text = bot.send_message.call_args.kwargs['text']
    assert 'ส่งเมลไม่สำเร็จ 2 รายการ' in text
    assert 'คืนเครดิต 0.6 credit แล้ว' in text
    assert 'ยอดคงเหลือ 1.2 credit' in text
    assert '@' not in text


def test_file_delivery_contains_only_email_lines():
    service = FakeService([{'id': 4, 'topic': 'telegram_document', 'payload': {'user_id': 42, 'order_id': 'o', 'emails': ['a@example.org']}, 'attempts': 1}])
    bot = SimpleNamespace(send_document=AsyncMock())
    asyncio.run(OutboxWorker(service, bot, SimpleNamespace()).run_once())
    assert bot.send_document.call_args.kwargs['document'].data == b'a@example.org\n'


def test_delivery_finishes_without_a_second_order_completion_query():
    from unittest.mock import Mock

    service = FakeService([{'id': 8, 'topic': 'telegram_text', 'payload': {
        'user_id': 42, 'order_id': 'o', 'text': 'a@example.org'}, 'attempts': 1}])
    service.mark_order_delivered = Mock(side_effect=AssertionError('finish_outbox owns order completion'))
    bot = SimpleNamespace(send_message=AsyncMock())
    asyncio.run(OutboxWorker(service, bot, SimpleNamespace()).run_once())
    assert service.finished[0][1] is True
    service.mark_order_delivered.assert_not_called()
