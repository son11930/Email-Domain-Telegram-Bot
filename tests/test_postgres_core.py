"""Real row-lock tests, enabled only with a dedicated TEST_DATABASE_URL."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from team_mail_bot.core import AppService, DomainError
from team_mail_bot.db import create_session_factory, init_db


@pytest.fixture
def pg_service():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is required for real PostgreSQL concurrency checks')
    schema = 'test_team_mail_' + uuid4().hex
    admin_engine = create_engine(url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    test_url = make_url(url).update_query_dict({'options': f'-csearch_path={schema}'})
    factory = create_session_factory(test_url)
    init_db(factory)
    yield AppService(factory)
    factory.kw['bind'].dispose()
    with admin_engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin_engine.dispose()


def test_postgres_last_email_race(pg_service):
    service = pg_service
    for user in (7, 8):
        service.ensure_user(user)
        service.adjust_credit(1, user, delta_units=100_000_000, reason='seed', request_key=str(user))
    service.import_emails(1, 'last@example.org')
    def buy(user):
        try:
            return service.purchase(user, 1, str(user))
        except DomainError:
            return None
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(buy, (7, 8)))
    assert sum(result is not None for result in results) == 1
    assert sum(service.get_user(user)['balance_units'] for user in (7, 8)) == 170_000_000


def test_postgres_duplicate_callback_race(pg_service):
    service = pg_service
    service.ensure_user(7)
    service.adjust_credit(1, 7, delta_units=100_000_000, reason='seed', request_key='seed')
    service.import_emails(1, 'one@example.org\ntwo@example.org')
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(lambda _: service.purchase(7, 1, 'same'), range(2)))
    assert results[0]['id'] == results[1]['id']
    assert service.get_user(7)['balance_units'] == 70_000_000
    assert len(service.list_emails()) == 1


def test_postgres_duplicate_payment_race(pg_service):
    from datetime import datetime
    service = pg_service
    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    def process(_):
        return service.record_payment('unique-transaction', topup['expected_units'], 'USDT', datetime.now(UTC))
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(process, range(2)))
    assert all(row['status'] == 'paid' for row in results)
    assert service.get_user(7)['balance_units'] == topup['expected_units']
    assert len(service.history(7)['ledger']) == 1


def test_postgres_duplicate_bank_slip_race_credits_once(pg_service):
    from datetime import datetime, timedelta

    service = pg_service
    service.ensure_user(7)
    topup = service.create_bank_topup(7, 15_000)
    occurred_at = datetime.fromisoformat(topup['created_at']) + timedelta(seconds=2)
    def process(_):
        return service.complete_bank_topup(7, topup['id'], 'unique-bank-slip',
                                           topup['expected_satang'], occurred_at)
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(process, range(2)))
    assert all(row['status'] == 'paid' for row in results)
    assert service.get_user(7)['balance_units'] == topup['credited_units']
    assert len(service.history(7)['ledger']) == 1

def test_postgres_distinct_payments_cannot_double_credit_reservation(pg_service, monkeypatch):
    from datetime import datetime
    from threading import Barrier
    service = pg_service
    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    barrier = Barrier(2)
    original_user = service._user
    def synchronized_user(session, user_id, lock=False):
        if lock:
            barrier.wait(timeout=10)
        return original_user(session, user_id, lock)
    monkeypatch.setattr(service, '_user', synchronized_user)
    def process(index):
        return service.record_payment(f'distinct-{index}', topup['expected_units'], 'USDT', datetime.now(UTC))
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(process, range(2)))
    assert sorted(row['status'] for row in results) == ['needs_review', 'paid']
    assert service.get_user(7)['balance_units'] == topup['expected_units']
    assert len(service.history(7)['ledger']) == 1

def test_postgres_rls_and_public_api_roles_cannot_read_wallet(pg_service):
    from sqlalchemy.exc import DBAPIError

    from team_mail_bot.models import Base
    service = pg_service
    service.ensure_user(7, 'private')
    engine = service.factory.kw['bind']
    created = []
    with engine.begin() as connection:
        schema = connection.scalar(text('SELECT current_schema()'))
        for role in ('anon', 'authenticated'):
            exists = connection.scalar(text('SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)'), {'role': role})
            if not exists:
                connection.execute(text(f'CREATE ROLE {role} NOLOGIN'))
                created.append(role)
            connection.execute(text(f'GRANT USAGE ON SCHEMA {schema} TO {role}'))
    try:
        init_db(service.factory)
        with engine.begin() as connection:
            rows = connection.execute(text('SELECT relname, relrowsecurity FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname=:schema AND relkind=\'r\''), {'schema': schema}).all()
            assert {row.relname for row in rows} == {table.name for table in Base.metadata.sorted_tables}
            assert all(row.relrowsecurity for row in rows)
        for role in ('anon', 'authenticated'):
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(f'SET LOCAL ROLE {role}'))
                connection.execute(text(f'SELECT * FROM {schema}.users')).all()
            with engine.begin() as connection:
                connection.execute(text(f'GRANT SELECT ON {schema}.users TO {role}'))
            with engine.begin() as connection:
                connection.execute(text(f'SET LOCAL ROLE {role}'))
                assert connection.execute(text(f'SELECT * FROM {schema}.users')).all() == []
            with engine.begin() as connection:
                connection.execute(text(f'REVOKE SELECT ON {schema}.users FROM {role}'))
    finally:
        with engine.begin() as connection:
            for role in ('anon', 'authenticated'):
                connection.execute(text(f'REVOKE USAGE ON SCHEMA {schema} FROM {role}'))
            for role in created:
                connection.execute(text(f'DROP ROLE {role}'))

def test_postgres_payment_cancel_race_resolves_once(pg_service, monkeypatch):
    from datetime import datetime
    from threading import Barrier
    service = pg_service
    service.ensure_user(7)
    topup = service.request_topup(7, 100_000_000)
    barrier = Barrier(2)
    original_user = service._user
    def synchronized_user(session, user_id, lock=False):
        if lock:
            barrier.wait(timeout=10)
        return original_user(session, user_id, lock)
    monkeypatch.setattr(service, '_user', synchronized_user)
    with ThreadPoolExecutor(2) as executor:
        payment = executor.submit(service.record_payment, 'payment-vs-cancel', topup['expected_units'], 'USDT', datetime.now(UTC))
        cancellation = executor.submit(service.cancel_topup, 7, topup['id'])
        paid_result = payment.result()
        cancellation.result()
    current = service.list_topups()[0]
    if current['status'] == 'paid':
        assert paid_result['status'] == 'paid'
        assert service.get_user(7)['balance_units'] == topup['expected_units']
        assert len(service.history(7)['ledger']) == 1
    else:
        assert current['status'] == 'cancelled'
        assert paid_result['status'] == 'needs_review'
        assert service.get_user(7)['balance_units'] == 0
        assert service.history(7)['ledger'] == []
