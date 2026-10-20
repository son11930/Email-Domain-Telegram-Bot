from datetime import UTC

import pytest

from team_mail_bot.core import AppService, DomainError
from team_mail_bot.db import create_session_factory, init_db


@pytest.fixture
def service():
    factory = create_session_factory('sqlite+pysqlite:///:memory:')
    init_db(factory)
    yield AppService(factory, topup_daily_limit=100, topup_cooldown_seconds=0)
    factory.kw['bind'].dispose()

def test_purchase_atomic_and_duplicate(service):
    service.ensure_user(7, 'Team')
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='credit')
    result = service.import_emails(1, '1.\nhello@sub.example.org|password@secret\n2. another@example.org\nhello@SUB.example.org')
    assert result == {'added': 2, 'duplicate': 1, 'invalid': 0}
    order = service.purchase(7, 2, 'nonce')
    assert order['total_units'] == 60_000_000
    assert order['balance_units'] == 40_000_000
    assert service.purchase(7, 2, 'nonce')['id'] == order['id']
    assert len(service.list_orders()) == 1
    with pytest.raises(DomainError):
        service.purchase(7, 2, 'other')
    assert service.get_user(7)['balance_units'] == 40_000_000

def test_topup_once_and_never_reuse(service):
    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    assert service.request_topup(7, 100_000_000)['id'] == topup['id']
    from datetime import datetime
    receipt = service.record_payment('tx1', topup['expected_units'], 'USDT', datetime.now(UTC))
    assert receipt['status'] == 'paid'
    assert service.record_payment('tx1', topup['expected_units'], 'USDT', datetime.now(UTC)) == receipt
    assert service.get_user(7)['balance_units'] == topup['expected_units']
    next_topup = service.request_topup(7, 100_000_000)
    assert next_topup['expected_units'] != topup['expected_units']

def test_parser_and_deleted_dedup(service):
    preview = service.preview_import('1.\nhello@sub.example.org|secret@bad.org\ninvalid\n2. other@example.net')
    assert preview['valid'] == ['hello@sub.example.org', 'other@example.net']
    assert preview['invalid'] == 1
    service.import_emails(1, 'hello@sub.example.org')
    row = service.list_emails()[0]
    service.delete_email(1, row['id'], 'bad')
    assert service.import_emails(1, 'hello@sub.example.org')['duplicate'] == 1

def test_credit_guard_and_outbox_retry(service):
    service.ensure_user(7)
    with pytest.raises(DomainError):
        service.adjust_credit(1, 7, delta_units=-1, reason='bad', request_key='bad')
    service.enqueue('test', {'ok': True}, 'key')
    service.enqueue('test', {'ok': False}, 'key')
    rows = service.claim_outbox()
    assert len(rows) == 1
    service.finish_outbox(rows[0]['id'], False, error='offline', retry_seconds=0, lease_token=rows[0]['lease_token'])
    assert service.claim_outbox()[0]['attempts'] == 2

def test_credit_idempotency_stale_form_and_audit(service):
    service.ensure_user(7)
    first = service.adjust_credit('web:owner-subject', 7, target_units=100_000_000,
                                  reason='opening', request_key='open', expected_balance_units=0)
    assert service.adjust_credit('web:owner-subject', 7, target_units=100_000_000,
                                 reason='opening', request_key='open', expected_balance_units=0) == first
    with pytest.raises(DomainError, match='Balance changed'):
        service.adjust_credit(1, 7, target_units=0, reason='stale', request_key='stale', expected_balance_units=0)
    assert len(service.list_audit()) == 1
    assert len(service.history(7)['ledger']) == 1
    assert service.list_users('7')[0]['id'] == 7
    assert service.summary()['users'] == 1


def test_delayed_discovery_and_late_payment(service):
    from datetime import datetime, timedelta

    from team_mail_bot.models import Topup
    service.ensure_user(7)
    first = service.request_topup(7, 100_000_000)
    created = datetime.fromisoformat(first['created_at'])
    with service.factory.begin() as session:
        row = session.get(Topup, first['id'])
        row.status = 'expired'
    assert service.record_payment('delayed', first['expected_units'], 'USDT', created + timedelta(seconds=1))['status'] == 'paid'
    second = service.request_topup(7, 100_000_000)
    late = datetime.fromisoformat(second['expires_at']) + timedelta(seconds=1)
    assert service.record_payment('late', second['expected_units'], 'USDT', late)['status'] == 'needs_review'
    assert service.record_payment('unknown', 99, 'USDT', datetime.now(UTC))['status'] == 'needs_review'
    assert service.record_payment('wrong-coin', second['expected_units'], 'BTC', datetime.now(UTC))['status'] == 'needs_review'
    assert service.get_user(7)['balance_units'] == first['expected_units']
    service.cancel_topup(7, second['id'])
    assert service.record_payment('cancelled', second['expected_units'], 'USDT', datetime.now(UTC))['status'] == 'needs_review'
    assert service.summary()['needs_review'] == 4
    assert len(service.list_topups()) == 2


def test_maximum_binance_transaction_id_survives_manual_review(service):
    from datetime import datetime

    transaction_id = 'x' * 256
    service.ensure_user(7)
    assert service.record_payment(transaction_id, 1, 'USDT', datetime.now(UTC))['status'] == 'needs_review'
    result = service.review_payment(1, transaction_id, 7, 'verified from Binance', 'review-long-id')
    assert result['status'] == 'paid'
    assert service.get_user(7)['balance_units'] == 1
    with pytest.raises(DomainError, match='transaction ID'):
        service.record_payment('y' * 257, 1, 'USDT', datetime.now(UTC))


def test_user_and_email_search_are_applied_in_database(service):
    from sqlalchemy import event

    service.ensure_user(7, 'Team Member')
    service.import_emails(1, '\n'.join(f'user{index}@example.org' for index in range(50)))
    statements = []
    engine = service.factory.kw['bind']

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith('select'):
            statements.append(statement.lower())

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        assert [row['id'] for row in service.list_users('tEAM')] == [7]
        assert [row['email'] for row in service.list_emails(query='USER49@')] == ['user49@example.org']
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert all(' limit ' not in statement for statement in statements)
    assert any(' like ' in statement or ' ilike ' in statement for statement in statements)


def test_outbox_delivery_status_and_owner_checks(service):
    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='seed')
    service.import_emails(1, 'a@example.net')
    with pytest.raises(DomainError, match='Price changed'):
        service.purchase(7, 1, 'price', expected_price_units=1)
    order = service.purchase(7, 1, 'one')
    with pytest.raises(DomainError):
        service.get_order(8, order['id'])
    service.enqueue('telegram_document', {'order_id': order['id'], 'user_id': 7}, 'document:' + order['id'])
    service.enqueue('telegram_text', {'order_id': order['id'], 'user_id': 7}, 'text:' + order['id'])
    rows = service.claim_outbox()
    assert len(rows) == 4
    assert service.claim_outbox() == []
    for row in rows:
        service.finish_outbox(row['id'], True, lease_token=row['lease_token'])
    assert service.get_order(7, order['id'])['status'] == 'delivered'
    assert service.summary()['pending_outbox'] == 0
    with pytest.raises(DomainError):
        service.delete_email(1, service.list_emails('sold')[0]['id'], 'sold')
    assert len(service.list_emails('all', 'EXAMPLE')) == 1


def test_amount_space_exhausted_and_checkpoint(service):
    from datetime import datetime, timedelta

    from team_mail_bot.core import AppService
    service = AppService(service.factory, precision=3, topup_daily_limit=100, topup_cooldown_seconds=0)
    service.ensure_user(7)
    amounts = []
    for _ in range(9):
        row = service.request_topup(7, 100_000_000)
        amounts.append(row['expected_units'])
        service.cancel_topup(7, row['id'])
    assert len(set(amounts)) == 9
    with pytest.raises(DomainError, match='No unique'):
        service.request_topup(7, 100_000_000)
    now = datetime.now(UTC)
    assert service.get_checkpoint('pay') is None
    service.set_checkpoint('pay', now)
    service.set_checkpoint('pay', now - timedelta(days=1))
    assert service.get_checkpoint('pay') == now


@pytest.mark.parametrize('operation', [
    lambda s: s.ensure_user(0),
    lambda s: s.ensure_user(1, None),
    lambda s: s.request_topup(7, 1),
    lambda s: s.purchase(7, True, 'x'),
    lambda s: s.purchase(7, 1, ''),
    lambda s: s.adjust_credit(1, 7, reason='x', request_key='x'),
    lambda s: s.adjust_credit(1, 7, delta_units=1, reason='', request_key='x'),
    lambda s: s.import_emails('untrusted', 'x@example.net'),
    lambda s: s.list_emails('bad'),
    lambda s: s.preview_import(None),
    lambda s: s.get_user(999),
    lambda s: s.finish_outbox(999, True),
    lambda s: s.cancel_topup(7, 'missing'),
])
def test_invalid_operations(service, operation):
    service.ensure_user(7)
    with pytest.raises(DomainError):
        operation(service)

def test_price_persists_and_refund_is_once(service):
    from team_mail_bot.core import AppService
    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='seed')
    service.import_emails(1, 'a@example.org')
    assert service.set_price(1, 20_000_000, 'new rate') == {'price_units': 20_000_000}
    restarted = AppService(service.factory)
    assert restarted.get_price() == 20_000_000
    order = restarted.purchase(7, 1, 'one', expected_price_units=20_000_000)
    assert order['total_units'] == 20_000_000
    assert restarted.refund_order(1, order['id'], 'delivery disputed', 'refund')['balance_units'] == 100_000_000
    assert restarted.refund_order(1, order['id'], 'retry', 'other')['balance_units'] == 100_000_000
    for notification in restarted.claim_outbox():
        restarted.finish_outbox(notification['id'], True, lease_token=notification['lease_token'])
    assert restarted.get_order(7, order['id'])['status'] == 'refunded'
    assert restarted.list_emails('sold')[0]['email'] == 'a@example.org'
    assert len(restarted.history(7)['ledger']) == 3


def test_manual_review_once_and_blocks_later_payment(service):
    from datetime import datetime, timedelta
    service.ensure_user(7)
    service.ensure_user(8)
    topup = service.request_topup(7, 100_000_000)
    late = datetime.fromisoformat(topup['expires_at']) + timedelta(seconds=1)
    service.record_payment('late', topup['expected_units'], 'USDT', late)
    with pytest.raises(DomainError, match='another user'):
        service.review_payment(1, 'late', 8, 'wrong owner', 'wrong')
    reviewed = service.review_payment(1, 'late', 7, 'verified', 'review')
    assert reviewed['balance_units'] == topup['expected_units']
    assert service.review_payment(1, 'late', 7, 'retry', 'review') == reviewed
    assert service.record_payment('second', topup['expected_units'], 'USDT', datetime.now(UTC))['status'] == 'needs_review'
    with pytest.raises(DomainError, match='already been credited'):
        service.review_payment(1, 'second', 7, 'duplicate amount', 'second')
    assert service.get_user(7)['balance_units'] == topup['expected_units']
    service.record_payment('unknown', 99, 'USDT', datetime.now(UTC))
    assert service.review_payment(1, 'unknown', 8, 'verified', 'unknown')['balance_units'] == 99
    with pytest.raises(DomainError):
        service.review_payment(1, 'unknown', 7, 'wrong', 'wrong')

def test_persistent_topup_issuance_limits(service, monkeypatch):
    from datetime import timedelta

    from team_mail_bot import core
    now = core.utcnow()
    monkeypatch.setattr(core, 'utcnow', lambda: now)
    limited = AppService(service.factory)
    limited.ensure_user(7)
    for index in range(3):
        now += timedelta(seconds=61)
        topup = limited.request_topup(7, 100_000_000)
        limited.cancel_topup(7, topup['id'])
        restarted = AppService(service.factory)
        with pytest.raises(DomainError, match='wait'):
            restarted.request_topup(7, 100_000_000)
    now += timedelta(seconds=61)
    with pytest.raises(DomainError, match='24 hours'):
        limited.request_topup(7, 200_000_000)
    now += timedelta(days=1)
    assert limited.request_topup(7, 100_000_000)['id'] != topup['id']


def test_outbox_stale_lease_cannot_regress_done(service, monkeypatch):
    from datetime import timedelta

    from team_mail_bot import core
    now = core.utcnow()
    monkeypatch.setattr(core, 'utcnow', lambda: now)
    service.enqueue('test', {}, 'lease-test')
    first = service.claim_outbox(1)[0]
    now += timedelta(seconds=301)
    second = service.claim_outbox(1)[0]
    assert second['lease_token'] != first['lease_token']
    assert service.finish_outbox(first['id'], False, lease_token=first['lease_token']) is False
    assert service.finish_outbox(second['id'], True, lease_token=second['lease_token']) is True
    assert service.finish_outbox(first['id'], False, lease_token=first['lease_token']) is False
    assert service.claim_outbox() == []


def test_refund_cancels_all_unsent_delivery_parts(service):
    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='seed')
    service.import_emails(1, 'refund@example.org')
    order = service.purchase(7, 1, 'refund-purchase')
    service.enqueue('telegram_text', {'order_id': order['id'], 'user_id': 7}, 'text-refund')
    claimed = service.claim_outbox()
    service.refund_order(1, order['id'], 'stop delivery', 'refund')
    for job in claimed:
        if job['topic'].startswith('telegram_'):
            assert service.finish_outbox(job['id'], False, lease_token=job['lease_token']) is False
    assert all(not job['topic'].startswith('telegram_') for job in service.claim_outbox())
    assert service.get_order(7, order['id'])['status'] == 'refunded'


@pytest.mark.parametrize('scheme', ['postgresql', 'postgres'])
def test_database_url_uses_installed_psycopg_driver(scheme):
    factory = create_session_factory(f'{scheme}://local_test@127.0.0.1:55432/postgres')
    try:
        assert factory.kw['bind'].url.drivername == 'postgresql+psycopg'
        assert factory.kw['bind'].dialect.driver == 'psycopg'
    finally:
        factory.kw['bind'].dispose()

def test_paid_requests_do_not_consume_daily_issuance_budget(service, monkeypatch):
    from datetime import timedelta

    from team_mail_bot import core
    now = core.utcnow()
    monkeypatch.setattr(core, 'utcnow', lambda: now)
    limited = AppService(service.factory)
    limited.ensure_user(7)
    for index in range(5):
        now += timedelta(seconds=61)
        topup = limited.request_topup(7, 100_000_000)
        assert limited.record_payment(f'legitimate-{index}', topup['expected_units'], 'USDT', now)['status'] == 'paid'
    assert len(limited.history(7)['topups']) == 5

def test_bulk_delete_atomic_and_deduplicated(service):
    service.import_emails(1, 'a@example.org\nb@example.org\nc@example.org')
    ids = [row['id'] for row in service.list_emails()]
    assert service.delete_emails('web:owner', [ids[0], ids[0], ids[1]], 'cleanup') == {'deleted': 2}
    assert len(service.list_emails('deleted')) == 2
    remaining = service.list_emails()[0]['id']
    for invalid_id in (ids[0], 9999):
        with pytest.raises(DomainError):
            service.delete_emails(1, [remaining, invalid_id], 'atomic')
        assert service.list_emails()[0]['id'] == remaining
    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='seed')
    service.purchase(7, 1, 'sold')
    service.import_emails(1, 'new@example.org')
    available_id = service.list_emails()[0]['id']
    with pytest.raises(DomainError):
        service.delete_emails(1, [available_id, remaining], 'allocated')
    assert service.list_emails()[0]['id'] == available_id
    assert len([event for event in service.list_audit() if event['action'] == 'delete_emails']) == 1


@pytest.mark.parametrize('ids', [[], [True], [-1], ['1'], [1.0], list(range(1, 502)), '1'])
def test_bulk_delete_rejects_invalid_identifiers(service, ids):
    with pytest.raises(DomainError):
        service.delete_emails(1, ids, 'invalid')


def test_import_batches_database_inserts_and_counts_concurrent_duplicates(service, monkeypatch):
    from sqlalchemy import event

    service.import_emails(1, 'duplicate@example.org')
    emails = ['duplicate@example.org'] + [f'batch{index}@example.org' for index in range(1200)]
    monkeypatch.setattr(service, 'preview_import', lambda text: {'valid': emails, 'duplicates': 0, 'invalid': 0})
    inserts = []
    engine = service.factory.kw['bind']

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith('insert into email_inventory'):
            inserts.append(statement)

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = service.import_emails(1, 'already previewed')
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert result == {'added': 1200, 'duplicate': 1, 'invalid': 0}
    assert len(inserts) <= 4, 'Import should use bounded batches rather than one remote query per email'


def test_purchase_uses_shared_price_lock_but_price_changes_remain_exclusive(service):
    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql

    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='shared-price-seed')
    service.import_emails(1, 'shared-price@example.org')
    statements = []

    def capture(state):
        if getattr(state.statement, 'is_select', False):
            sql = str(state.statement.compile(dialect=postgresql.dialect()))
            if 'FROM settings' in sql:
                statements.append(sql)

    event.listen(service.factory, 'do_orm_execute', capture)
    try:
        service.purchase(7, 1, 'shared-price')
        assert any('FOR SHARE' in sql for sql in statements)
        statements.clear()
        service.set_price(1, 20_000_000, 'new price')
        assert any('FOR UPDATE' in sql for sql in statements)
    finally:
        event.remove(service.factory, 'do_orm_execute', capture)


def test_stock_read_counts_only_available_inventory_in_one_query(service):
    from sqlalchemy import event

    service.import_emails(1, 'available@example.org\ndeleted@example.org')
    deleted = service.list_emails(query='deleted')[0]
    service.delete_email(1, deleted['id'], 'exclude deleted')
    statements = []
    engine = service.factory.kw['bind']

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        assert service.get_stock() == 1
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(statements) == 1
    assert 'count(' in statements[0].lower()
