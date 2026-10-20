"""Complete public-user flow with real services and mocked external transports."""
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from team_mail_bot.core import AppService
from team_mail_bot.db import create_session_factory, init_db
from team_mail_bot.payments import BinancePayClient, PaymentPoller
from team_mail_bot.telegram_bot import TelegramController
from team_mail_bot.workers import OutboxWorker


class State:
    def __init__(self):
        self.data, self.name = {}, None
    async def clear(self):
        self.data, self.name = {}, None
    async def get_data(self):
        return self.data
    async def get_state(self):
        return self.name
    async def set_state(self, name):
        self.name = name
    async def update_data(self, **values):
        self.data = {**self.data, **values}


def test_public_signup_payment_purchase_and_dual_delivery():
    async def scenario():
        factory = create_session_factory('sqlite://')
        init_db(factory)
        service = AppService(factory)
        settings = SimpleNamespace(admin_ids=frozenset({99}), owner_id=99,
            price_units=30000000, max_order_quantity=1000, binance_receiver_id='12345')
        controller = TelegramController(service, settings)
        state = State()
        message = SimpleNamespace(from_user=SimpleNamespace(id=7, full_name='New user'),
            chat=SimpleNamespace(type='private'), text='/start', document=None, answer=AsyncMock())
        await controller.message(message, state)
        assert service.get_user(7)['balance_units'] == 0
        service.import_emails(99, '1. a@sub.example.org|secret\n2. b@example.net|secret')
        topup = service.request_topup(7, 100000000)
        now = datetime.now(UTC)
        from decimal import Decimal
        amount = format(Decimal(topup['expected_units']) / 100000000, 'f')
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'code': '000000', 'success': True, 'data': [{
                'transactionId': 'actual-provider-id', 'transactionTime': int(now.timestamp() * 1000),
                'amount': amount, 'currency': 'USDT', 'orderType': 'C2C',
                'receiverInfo': {'binanceId': '12345'}, 'payerInfo': {'name': 'Sender'}}]})))
        poller = PaymentPoller(BinancePayClient('test-key', 'test-secret', '12345', client=client), service)
        poller.poll_once(now=now)
        poller.poll_once(now=now)
        assert service.get_user(7)['balance_units'] == topup['expected_units']
        await state.set_state('bulk')
        message.text = '2'
        await controller.message(message, state)
        preview = message.answer.await_args.kwargs['reply_markup']
        confirmation = preview.inline_keyboard[0][0].callback_data
        callback = SimpleNamespace(from_user=message.from_user, message=message,
                                   data=confirmation, answer=AsyncMock())
        await controller.callback(callback, state)
        orders = service.history(7)['orders']
        assert len(orders) == 1
        assert service.get_user(7)['balance_units'] == topup['expected_units'] - 60000000
        bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())
        class Discord:
            def __init__(self):
                self.events = []
            def send(self, topic, payload):
                self.events.append((topic, payload))
        discord = Discord()
        worker = OutboxWorker(service, bot, discord)
        for _ in range(20):
            if not await worker.run_once():
                break
        assert bot.send_document.await_count == 1
        assert bot.send_document.await_args.kwargs['document'].data == b'a@sub.example.org\nb@example.net\n'
        text = '\n'.join(call.kwargs['text'] for call in bot.send_message.await_args_list)
        assert 'a@sub.example.org\nb@example.net' in text
        assert 'secret' not in text
        assert {topic for topic, _ in discord.events} == {'discord_topup', 'discord_order'}
        assert len(discord.events) == 2
        assert service.get_order(7, orders[0]['id'])['status'] == 'delivered'
        assert service.summary()['pending_outbox'] == 0
        factory.kw['bind'].dispose()
    asyncio.run(scenario())
