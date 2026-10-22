from datetime import UTC, datetime

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


def test_purchase_can_skip_email_hydration_for_outbox_only_callers(service, monkeypatch):
    service.ensure_user(7, 'Team')
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='credit')
    service.import_emails(1, 'a@example.org')
    with monkeypatch.context() as purchase_context:
        purchase_context.setattr(service, '_order', lambda *_: (_ for _ in ()).throw(
            AssertionError('purchase should not fetch email bodies for this caller')))
        order = service.purchase(7, 1, 'fast-path', include_emails=False)

    assert order['id']
    assert 'emails' not in order
    assert service.get_order(7, order['id'])['emails'] == ['a@example.org']

def test_purchase_waits_for_final_discord_notification_and_suppresses_legacy_pending(service):
    service.ensure_user(7, 'Team Member')
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='credit')
    service.import_emails(1, 'a@example.org')
    service.purchase(7, 1, 'order')
    service.enqueue('discord_order', {'order_id': 'old', 'status': 'pending'}, 'legacy-pending')

    jobs = service.claim_outbox()

    assert all(not (job['topic'] == 'discord_order' and job['payload'].get('status') == 'pending')
               for job in jobs)
    assert [job['topic'] for job in jobs] == ['telegram_order']

def test_refund_enqueues_final_failure_status_with_user_name(service):
    service.ensure_user(7, 'Team Member')
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='credit')
    service.import_emails(1, 'a@example.org')
    order = service.purchase(7, 1, 'order')

    service.refund_order(1, order['id'], 'คืนเครดิตตามคำขอ', 'refund')
    jobs = service.claim_outbox()
    notification = next(job for job in jobs if job['topic'] == 'discord_order')

    assert notification['payload']['status'] == 'refunded'
    assert notification['payload']['user_name'] == 'Team Member'
    assert notification['payload']['failure_reason'] == 'คืนเครดิตตามคำขอ'


def test_admin_orders_complete_without_discord_order_notifications(service):
    admin_service = AppService(service.factory, admin_ids={7, 8})
    admin_service.ensure_user(7, 'Owner')
    admin_service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='admin-seed')
    admin_service.import_emails(1, 'owner@example.org')
    order = admin_service.purchase(7, 1, 'admin-order')
    admin_service.enqueue('telegram_text', {'order_id': order['id'], 'user_id': 7,
        'text': 'owner@example.org'}, 'admin-order-text')

    for job in admin_service.claim_outbox():
        admin_service.finish_outbox(job['id'], True, lease_token=job['lease_token'])

    assert admin_service.get_order(7, order['id'])['status'] == 'delivered'
    assert admin_service.claim_outbox() == []

    admin_service.ensure_user(8, 'Admin')
    admin_service.adjust_credit(1, 8, delta_units=100_000_000, reason='seed', request_key='admin-seed-8')
    admin_service.import_emails(1, 'admin@example.org')
    order = admin_service.purchase(8, 1, 'admin-order-8')
    admin_service.refund_order(1, order['id'], 'test refund', 'admin-refund-8')
    assert admin_service.claim_outbox() == []


def test_expired_topups_are_marked_without_new_user_request(service, monkeypatch):
    from datetime import timedelta

    from team_mail_bot import core
    now = core.utcnow()
    monkeypatch.setattr(core, 'utcnow', lambda: now)
    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    now += timedelta(seconds=481)

    assert service.expire_topups() == 1
    assert service.list_topups()[0]['status'] == 'expired'
    result = service.record_payment('too-late', topup['expected_units'], 'USDT', now)
    assert result['status'] == 'needs_review'
    assert service.get_user(7)['balance_units'] == 0


def test_dashboard_counts_only_successful_topup_payments(service):
    from datetime import datetime, timedelta

    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    created = datetime.fromisoformat(topup['created_at'])
    assert service.summary()['successful_topups'] == 0

    service.record_payment('success-topup', topup['expected_units'], 'USDT', created + timedelta(seconds=1))

    assert service.summary()['successful_topups'] == 1

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

def test_bank_topup_converts_randomized_satang_and_credits_once(service):
    from datetime import timedelta

    from team_mail_bot.core import bank_satang_to_units

    service.ensure_user(7)
    topup = service.create_bank_topup(7, 15_000)
    assert 15_001 <= topup['expected_satang'] <= 15_099
    assert topup['credited_units'] == bank_satang_to_units(topup['expected_satang'])
    occurred_at = datetime.fromisoformat(topup['created_at']) + timedelta(minutes=1)
    result = service.complete_bank_topup(7, topup['id'], 'SCB-TX-1',
                                         topup['expected_satang'], occurred_at)
    assert result['status'] == 'paid'
    assert service.complete_bank_topup(7, topup['id'], 'SCB-TX-1',
                                       topup['expected_satang'], occurred_at)['status'] == 'paid'
    assert service.get_user(7)['balance_units'] == topup['credited_units']

def test_bank_topup_rejects_late_and_wrong_amount_without_credit(service):
    from datetime import timedelta

    service.ensure_user(7)
    topup = service.create_bank_topup(7, 15_000)
    expiry = datetime.fromisoformat(topup['expires_at'])
    late = service.complete_bank_topup(7, topup['id'], 'SCB-LATE',
                                       topup['expected_satang'], expiry + timedelta(seconds=1))
    assert late['status'] == 'needs_review'
    assert service.get_user(7)['balance_units'] == 0
    wrong = service.complete_bank_topup(7, topup['id'], 'SCB-WRONG',
                                        topup['expected_satang'] + 1,
                                        datetime.fromisoformat(topup['created_at']) + timedelta(seconds=10))
    assert wrong['status'] == 'needs_review'
    assert service.get_user(7)['balance_units'] == 0

def test_bank_topup_minimum_unique_amount_and_expired_timely_transfer(service):
    from datetime import timedelta

    service.ensure_user(7)
    with pytest.raises(DomainError):
        service.create_bank_topup(7, 14_999)
    first = service.create_bank_topup(7, 15_000)
    service.expire_bank_topups(now=datetime.fromisoformat(first['expires_at']) + timedelta(seconds=1))
    paid_time = datetime.fromisoformat(first['created_at']) + timedelta(minutes=14)
    second = service.create_bank_topup(7, 15_000)
    assert second['expected_satang'] != first['expected_satang']
    assert service.complete_bank_topup(7, first['id'], 'SCB-TIMELY-LATE-UPLOAD',
                                       first['expected_satang'], paid_time)['status'] == 'paid'

def test_cancelled_bank_topup_and_duplicate_reference_never_credit_twice(service):
    from datetime import timedelta

    service.ensure_user(7)
    cancelled = service.create_bank_topup(7, 15_000)
    service.cancel_bank_topup(7, cancelled['id'])
    sent_at = datetime.fromisoformat(cancelled['created_at']) + timedelta(seconds=3)
    assert service.complete_bank_topup(7, cancelled['id'], 'SCB-CANCELLED',
        cancelled['expected_satang'], sent_at)['status'] == 'needs_review'
    assert service.get_user(7)['balance_units'] == 0

    active = service.create_bank_topup(7, 15_000)
    assert service.complete_bank_topup(7, active['id'], 'SCB-UNIQUE',
        active['expected_satang'], datetime.fromisoformat(active['created_at']))['status'] == 'paid'
    service.ensure_user(8)
    second = service.create_bank_topup(8, 15_000)
    with pytest.raises(DomainError):
        service.complete_bank_topup(8, second['id'], 'SCB-UNIQUE',
            second['expected_satang'], datetime.fromisoformat(second['created_at']))
    assert service.get_user(8)['balance_units'] == 0


def test_bank_topup_is_in_admin_history_and_successful_summary(service):
    service.ensure_user(7)
    topup = service.create_bank_topup(7, 15_000)
    service.complete_bank_topup(7, topup['id'], 'SCB-SUMMARY', topup['expected_satang'],
        datetime.fromisoformat(topup['created_at']))

    row = service.list_topups()[0]
    assert row['provider'] == 'ธนาคาร'
    assert row['expected_satang'] == topup['expected_satang']
    assert row['credited_units'] == topup['credited_units']
    assert service.summary()['successful_topups'] == 1
    assert service.summary()['total_topup_units'] == topup['credited_units']

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
    assert len(rows) == 3
    assert service.claim_outbox() == []
    for row in rows:
        service.finish_outbox(row['id'], True, lease_token=row['lease_token'])
    assert service.get_order(7, order['id'])['status'] == 'delivered'
    final_notice, = service.claim_outbox()
    assert final_notice['topic'] == 'discord_order'
    assert final_notice['payload']['status'] == 'success'
    service.finish_outbox(final_notice['id'], True, lease_token=final_notice['lease_token'])
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


def test_slip_verification_is_limited_to_five_attempts_per_bangkok_day(service):
    from datetime import datetime

    service.ensure_user(7, 'User')
    now = datetime.fromisoformat('2026-10-22T17:00:00+00:00')  # midnight in Bangkok
    for slot in range(1, 6):
        assert service.reserve_slip_verification(7, f'{slot:064x}', now) == slot
    with pytest.raises(DomainError, match='5 ครั้งต่อวันตามเวลาไทย'):
        service.reserve_slip_verification(7, f'{6:064x}', now)

    # The cap resets at midnight Thailand time, not midnight UTC.
    next_bangkok_day = datetime.fromisoformat('2026-10-23T17:00:00+00:00')
    assert service.reserve_slip_verification(7, f'{6:064x}', next_bangkok_day) == 1


def test_slip_verification_rejects_reused_image_hash_globally(service):
    service.ensure_user(7, 'User')
    service.ensure_user(8, 'Another user')
    digest = 'a' * 64
    assert service.reserve_slip_verification(7, digest) == 1
    with pytest.raises(DomainError, match='เคยส่งตรวจแล้ว'):
        service.reserve_slip_verification(8, digest)
    assert service.reserve_slip_verification(8, 'b' * 64) == 1


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'G' * 64, 'a' * 65])
def test_slip_verification_rejects_invalid_sha256(service, digest):
    service.ensure_user(7, 'User')
    with pytest.raises(DomainError, match='Invalid image hash'):
        service.reserve_slip_verification(7, digest)


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
