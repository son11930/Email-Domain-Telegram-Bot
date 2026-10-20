import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from team_mail_bot.telegram_bot import (
    ChatGuard,
    TelegramController,
    UserRateLimit,
    create_router,
    format_units,
    main_menu,
    parse_amount,
)


def run(coro):
    return asyncio.run(coro)


def settings():
    return SimpleNamespace(admin_ids=frozenset({99}), owner_id=99,
                           price_units=30_000_000, max_order_quantity=100,
                           binance_receiver_id='123456')


def message(user_id=1, text='/start', chat_type='private'):
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id, full_name='Team'),
                           chat=SimpleNamespace(type=chat_type), text=text,
                           document=None, answer=AsyncMock())


def state(data=None, name=None):
    return SimpleNamespace(clear=AsyncMock(), get_data=AsyncMock(return_value=data or {}),
                           get_state=AsyncMock(return_value=name),
                           set_state=AsyncMock(), update_data=AsyncMock())


def service():
    return SimpleNamespace(ensure_user=Mock(return_value={'balance_units': 100_000_000}),
                           get_user=Mock(return_value={'name': 'Team', 'balance_units': 100_000_000}),
                           summary=Mock(return_value={'available': 5}),
                           get_price=Mock(return_value=30_000_000),
                           get_stock=Mock(return_value=5),
                           purchase=Mock(return_value={'id': 'order1'}))


def test_money_is_exact_and_bounded():
    assert format_units(100_370_000) == '1.0037'
    assert parse_amount('1.20', decimals=2) == 120_000_000
    for value in ['NaN', 'Infinity', '1e3', '-1', '0', '1.234', '9' * 100]:
        with pytest.raises(ValueError):
            parse_amount(value, decimals=2)


def test_public_start_creates_user_and_private_guard():
    svc = service()
    controller = TelegramController(svc, settings())
    msg = message()
    run(controller.message(msg, state()))
    svc.ensure_user.assert_called_once_with(1, 'Team')
    assert msg.answer.await_args.kwargs['reply_markup']
    run(controller.message(message(chat_type='group'), state()))
    assert svc.ensure_user.call_count == 1


def test_main_menu_shows_name_with_telegram_id():
    svc = service()
    svc.get_user.return_value = {'name': 'Team Member', 'balance_units': 100_000_000}
    controller = TelegramController(svc, settings())
    msg = message()

    run(controller.message(msg, state()))

    assert 'ชื่อ: Team Member' in msg.answer.await_args.args[0]
    assert 'รหัสผู้ใช้: 1' in msg.answer.await_args.args[0]


def test_quick_buttons_bind_user_and_nonce():
    first = main_menu(1, 30_000_000, False)
    second = main_menu(1, 30_000_000, False)
    token = first.inline_keyboard[0][0].callback_data
    assert token.startswith('q:1:30000000:')
    assert len(token.encode()) <= 64
    assert token != second.inline_keyboard[0][0].callback_data


def test_quick_purchase_rejects_forged_owner_and_reuses_key():
    svc = service()
    controller = TelegramController(svc, settings())
    cb = SimpleNamespace(from_user=SimpleNamespace(id=1), message=message(),
                         data='q:2:30000000:abc', answer=AsyncMock())
    run(controller.callback(cb, state()))
    svc.purchase.assert_not_called()
    cb.data = 'q:1:30000000:abc'
    run(controller.callback(cb, state()))
    run(controller.callback(cb, state()))
    assert svc.purchase.call_args_list[0] == svc.purchase.call_args_list[1]


def test_admin_callback_and_stale_import_require_admin():
    svc = service()
    svc.import_emails = Mock()
    controller = TelegramController(svc, settings())
    cb = SimpleNamespace(from_user=SimpleNamespace(id=1), message=message(),
                         data='admin:import', answer=AsyncMock())
    run(controller.callback(cb, state()))
    run(controller.message(message(text='a@example.com'), state(name='admin_import')))
    svc.import_emails.assert_not_called()


def test_rate_limit_memory_bounded():
    limiter = UserRateLimit(capacity=4)
    for uid in range(100):
        limiter.allow(uid)
    assert len(limiter.entries) == 4
    assert not limiter.allow(99)


class MemoryState:
    def __init__(self, name=None, data=None):
        self.name, self.data = name, data or {}

    async def clear(self):
        self.name, self.data = None, {}

    async def get_state(self):
        return self.name

    async def set_state(self, value):
        self.name = value

    async def get_data(self):
        return self.data.copy()

    async def update_data(self, **kwargs):
        self.data = {**self.data, **kwargs}


def callback(data, uid=1):
    return SimpleNamespace(from_user=SimpleNamespace(id=uid), message=message(uid),
                           data=data, answer=AsyncMock())


def test_bulk_requires_confirmation_and_preserves_order_request_on_replay():
    svc, ui = service(), MemoryState()
    controller = TelegramController(svc, settings())
    run(controller.callback(callback('bulk'), ui))
    run(controller.message(message(text='2'), ui))
    svc.purchase.assert_not_called()
    token = ui.data['nonce']
    run(controller.callback(callback(f'buy:{token}'), ui))
    assert svc.purchase.call_args.args[1] == 2
    run(controller.callback(callback(f'buy:{token}'), ui))
    assert svc.purchase.call_args_list[0] == svc.purchase.call_args_list[1]
    run(controller.callback(callback('buy:expired'), ui))
    assert svc.purchase.call_count == 2


@pytest.mark.parametrize('quantity', ['0', '-1', '101', '1.5', 'abc'])
def test_bulk_rejects_invalid_count_without_purchase(quantity):
    svc = service()
    run(TelegramController(svc, settings()).message(message(text=quantity), MemoryState('bulk')))
    svc.purchase.assert_not_called()


def test_bulk_checks_balance_before_confirmation():
    svc, ui = service(), MemoryState('bulk')
    svc.get_user.return_value = {'balance_units': 1}
    msg = message(text='2')
    run(TelegramController(svc, settings()).message(msg, ui))
    assert 'เครดิตไม่เพียงพอ' in msg.answer.await_args.args[0]
    assert 'nonce' not in ui.data


def test_topup_preset_custom_and_cancel_show_exact_amount():
    svc, ui = service(), MemoryState()
    svc.request_topup = Mock(return_value={'id': 'topup-1', 'expected_units': 100_370_000,
                                           'expires_at': '2026-10-20T00:00:00+00:00'})
    svc.cancel_topup = Mock()
    controller = TelegramController(svc, settings())
    cb = callback('topup')
    run(controller.callback(cb, ui))
    assert ui.name == 'topup'
    msg = message(text='1')
    run(controller.message(msg, ui))
    displayed = msg.answer.await_args.args[0]
    assert '1.0037 USDT' in displayed and '123456' in displayed
    assert '07:00:00' in displayed
    run(controller.callback(callback('fund:5'), ui))
    assert svc.request_topup.call_args.args == (1, 500_000_000)
    run(controller.callback(callback('cancel:topup-1'), ui))
    svc.cancel_topup.assert_called_once_with(1, 'topup-1')


def test_stock_history_and_resend_only_owner_requested():
    svc = service()
    svc.get_stock.return_value = 7
    svc.history = Mock(return_value={'orders': [{'id': 'mine', 'quantity': 2}],
                                     'ledger': [{'delta_units': -60_000_000}]})
    svc.get_order = Mock(return_value={'id': 'mine'})
    svc.enqueue = Mock()
    controller = TelegramController(svc, settings())
    for action in ['stock', 'history', 'balance', 'resend:mine', 'unknown', 'menu']:
        run(controller.callback(callback(action), MemoryState()))
    svc.get_order.assert_called_once_with(1, 'mine')
    assert svc.enqueue.call_args.args[0] == 'telegram_order'
    assert svc.enqueue.call_args.args[1] == {'order_id': 'mine', 'user_id': 1}
    svc.purchase.assert_not_called()


def test_import_preview_discards_password_and_needs_confirmation():
    svc, ui = service(), MemoryState('admin_import')
    svc.preview_import = Mock(return_value={'valid': ['safe@example.org'], 'duplicates': 1, 'invalid': 0})
    svc.import_emails = Mock(return_value={'added': 1})
    controller = TelegramController(svc, settings())
    msg = message(99, '1. safe@example.org|super-private-password')
    run(controller.message(msg, ui))
    assert 'super-private-password' not in repr(ui.data)
    assert 'super-private-password' not in str(msg.answer.await_args)
    svc.import_emails.assert_not_called()
    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    svc.import_emails.assert_called_once_with(99, 'safe@example.org')
    assert ui.data == {}


def test_upload_utf8_is_parsed_and_oversized_or_wrong_extension_rejected():
    svc, ui = service(), MemoryState('admin_import')
    svc.preview_import = Mock(return_value={'valid': ['safe@example.org']})
    controller = TelegramController(svc, settings())
    msg = message(99, '')
    msg.document = SimpleNamespace(file_name='list.txt', file_size=22)
    msg.bot = SimpleNamespace(download=AsyncMock(return_value=BytesIO(b'safe@example.org')))
    run(controller.message(msg, ui))
    svc.preview_import.assert_called_once_with('safe@example.org')
    msg.document.file_size = 999999
    run(controller.message(msg, ui))
    msg.document.file_size, msg.document.file_name = 10, 'list.exe'
    run(controller.message(msg, ui))
    assert svc.preview_import.call_count == 1


def test_credit_preview_requires_reason_and_checks_atomic_expected_balance():
    svc, ui = service(), MemoryState('admin_credit')
    svc.adjust_credit = Mock()
    controller = TelegramController(svc, settings())
    run(controller.message(message(99, '1 target 2 audit reason'), ui))
    svc.adjust_credit.assert_not_called()
    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    assert svc.adjust_credit.call_args.kwargs['target_units'] == 200_000_000
    assert svc.adjust_credit.call_args.kwargs['expected_balance_units'] == 100_000_000
    run(controller.message(message(99, '1 delta -0.5 test reason'), ui := MemoryState('admin_credit')))
    svc.get_user.return_value = {'balance_units': 9}
    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    assert svc.adjust_credit.call_count == 1


def test_credit_adjustment_accepts_id_then_amount_and_generates_audit_reason():
    svc, ui = service(), MemoryState()
    svc.adjust_credit = Mock()
    controller = TelegramController(svc, settings())

    run(controller.message(message(99, '7'), ui := MemoryState('admin_credit')))
    assert ui.name == 'admin_credit_amount'
    assert ui.data['credit_user_id'] == 7
    svc.adjust_credit.assert_not_called()

    run(controller.message(message(99, '1.5'), ui))
    assert svc.adjust_credit.call_count == 0
    assert ui.data['operation'] == 'credit'
    assert ui.data['units'] == 150_000_000
    assert ui.data['mode'] == 'delta'

    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    svc.adjust_credit.assert_called_once()
    args, kwargs = svc.adjust_credit.call_args
    assert args[:2] == (99, 7)
    assert kwargs['delta_units'] == 150_000_000
    assert kwargs['expected_balance_units'] == 100_000_000
    assert kwargs['reason']


def test_credit_adjustment_accepts_id_and_signed_amount_in_one_message():
    svc, ui = service(), MemoryState('admin_credit')
    svc.adjust_credit = Mock()
    controller = TelegramController(svc, settings())

    run(controller.message(message(99, '7 -0.5'), ui))
    assert svc.adjust_credit.call_count == 0
    assert ui.data['units'] == -50_000_000
    assert ui.data['mode'] == 'delta'
    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    assert svc.adjust_credit.call_args.kwargs['delta_units'] == -50_000_000

    svc.get_user.return_value = {'balance_units': 100_000_000}
    retry_ui = MemoryState('admin_credit')
    run(controller.message(message(99, '7 -2'), retry_ui))
    assert svc.adjust_credit.call_count == 1
    assert retry_ui.name == 'admin_credit'
    run(controller.message(message(99, '7 1'), retry_ui))
    run(controller.callback(callback('confirm:' + retry_ui.data['nonce'], 99), retry_ui))
    assert svc.adjust_credit.call_count == 2


def test_selecting_new_credit_user_invalidates_previous_confirmation():
    svc, ui = service(), MemoryState('admin_credit')
    svc.adjust_credit = Mock()
    controller = TelegramController(svc, settings())

    run(controller.message(message(99, '7 1'), ui))
    previous_nonce = ui.data['nonce']
    run(controller.message(message(99, '8'), ui))
    assert ui.name == 'admin_credit_amount'
    run(controller.callback(callback('confirm:' + previous_nonce, 99), ui))
    svc.adjust_credit.assert_not_called()

    run(controller.message(message(99, '2'), ui))
    run(controller.callback(callback('confirm:' + ui.data['nonce'], 99), ui))
    assert svc.adjust_credit.call_args.args[:2] == (99, 8)
    for invalid in ['abc', '1 target -1 bad reason', '1 delta -10 good reason', '1 delta 1 x']:
        run(controller.message(message(99, invalid), MemoryState('admin_credit')))
    assert svc.adjust_credit.call_count == 1


def test_delete_and_admin_menu_maintain_guards_at_confirmation():
    svc, ui = service(), MemoryState()
    svc.delete_email = Mock()
    controller = TelegramController(svc, settings())
    for action in ['admin:menu', 'admin:credit', 'admin:import', 'admin:delete']:
        run(controller.callback(callback(action, 99), ui))
    run(controller.message(message(99, '5 remove damaged'), ui))
    token = ui.data['nonce']
    run(controller.callback(callback('confirm:' + token, 1), ui))
    svc.delete_email.assert_not_called()
    run(controller.callback(callback('confirm:' + token, 99), ui))
    svc.delete_email.assert_called_once_with(99, 5, 'remove damaged')
    run(controller.callback(callback('confirm:expired', 99), ui))
    run(controller.message(message(99, 'invalid'), MemoryState('admin_delete')))
    assert svc.delete_email.call_count == 1


def test_service_failure_does_not_reflect_secret_in_message():
    svc = service()
    svc.ensure_user.side_effect = RuntimeError('sensitive-db-password')
    msg = message()
    run(TelegramController(svc, settings()).message(msg, MemoryState()))
    assert 'sensitive-db-password' not in str(msg.answer.await_args)


def test_unknown_message_and_group_callbacks_are_safe():
    controller = TelegramController(service(), settings())
    msg = message(text='hello')
    run(controller.message(msg, MemoryState()))
    assert '/start' in msg.answer.await_args.args[0]
    cb = callback('q:1:30000000:abc')
    cb.message.chat.type = 'group'
    run(controller.callback(cb, MemoryState()))
    assert cb.answer.await_args.kwargs['show_alert']


def test_router_registers_guards_and_private_rate_limits():
    router = create_router(service(), settings())
    assert len(router.message.handlers) == 1
    guard, handler = ChatGuard(), AsyncMock()
    msg = message()
    run(guard(handler, msg, {}))
    run(guard(handler, msg, {}))
    assert handler.await_count == 1
    msg.chat.type = 'supergroup'
    run(guard(handler, msg, {}))
    assert handler.await_count == 1


def test_dispatcher_injects_fsm_and_routes_start_without_network(monkeypatch):
    svc, bot = service(), Bot('123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi')
    dispatch = Dispatcher()
    dispatch.include_router(create_router(svc, settings()))
    requests = AsyncMock(return_value=True)
    monkeypatch.setattr(Bot, '__call__', requests)
    update = Update.model_validate({'update_id': 1, 'message': {
        'message_id': 1, 'date': 0, 'chat': {'id': 1, 'type': 'private'},
        'from': {'id': 1, 'is_bot': False, 'first_name': 'New member'}, 'text': '/start'}})
    run(dispatch.feed_update(bot, update))
    svc.ensure_user.assert_called_once_with(1, 'New member')
    assert requests.await_count == 1
    run(bot.session.close())


def test_menu_stock_and_bulk_use_focused_reads_instead_of_global_summary():
    svc = service()
    svc.get_price = Mock(return_value=30_000_000)
    svc.get_stock = Mock(return_value=7)
    svc.summary.side_effect = AssertionError('Global statistics are not needed by public hot paths')
    controller = TelegramController(svc, settings())
    run(controller.menu(message(), 1))
    run(controller.bulk_preview(message(), MemoryState('bulk'), '2', 1))
    stock = callback('stock')
    run(controller.callback(stock, MemoryState()))
    assert '7' in stock.message.answer.await_args.args[0]
    assert svc.get_price.call_count == 2
    svc.get_stock.assert_called_once_with()
    svc.summary.assert_not_called()
