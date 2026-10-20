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
    def respond(request):
        import json
        payload = json.loads(request.content)
        assert payload['allowed_mentions'] == {'parse': []}
        assert 'stolen@example.org' not in str(payload)
        assert request.url.params['wait'] == 'true'
        return httpx.Response(200, json={'id': '123'})
    client = httpx.Client(transport=httpx.MockTransport(respond))
    notifier = DiscordNotifier('https://discord.com/api/webhooks/1/token', 'https://discord.com/api/webhooks/2/token', client=client)
    notifier.send('discord_order', {'order_id': 'abc', 'user_id': 42, 'quantity': 1,
                                  'total_units': 30000000, 'emails': ['stolen@example.org']})


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
                'quantity': 2, 'total_units': 60000000, 'balance_units': 40000000}
    def enqueue(self, topic, payload, dedupe_key):
        self.enqueued.append((topic, payload, dedupe_key))
    def finish_outbox(self, job_id, success, error='', retry_seconds=30, lease_token=None):
        self.finished.append((job_id, success, error, retry_seconds))
    def mark_order_delivered(self, order_id):
        pass


def test_order_expands_one_file_and_all_text_idempotent_keys():
    service = FakeService([{'id': 1, 'topic': 'telegram_order', 'payload': {'order_id': 'o', 'user_id': 42}, 'attempts': 1}])
    worker = OutboxWorker(service, SimpleNamespace(), SimpleNamespace())
    asyncio.run(worker.run_once())
    assert [topic for topic, _, _ in service.enqueued].count('telegram_document') == 1
    messages = [payload['text'] for topic, payload, _ in service.enqueued if topic == 'telegram_text']
    assert 'a@example.org\nb@example.org' in messages
    assert service.finished[0][1] is True


def test_transport_error_retries_same_part_without_purchase():
    service = FakeService([{'id': 3, 'topic': 'telegram_text', 'payload': {'user_id': 42, 'text': 'a@example.org', 'order_id': 'o'}, 'attempts': 1}])
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError('sensitive transport data')))
    asyncio.run(OutboxWorker(service, bot, SimpleNamespace()).run_once())
    assert service.finished[0][1] is False
    assert 'sensitive' not in service.finished[0][2]


def test_file_delivery_contains_only_email_lines():
    service = FakeService([{'id': 4, 'topic': 'telegram_document', 'payload': {'user_id': 42, 'order_id': 'o', 'emails': ['a@example.org']}, 'attempts': 1}])
    bot = SimpleNamespace(send_document=AsyncMock())
    asyncio.run(OutboxWorker(service, bot, SimpleNamespace()).run_once())
    assert bot.send_document.call_args.kwargs['document'].data == b'a@example.org\n'
