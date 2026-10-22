import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from team_mail_bot.admin_web import create_app


class Auth:
    def login(self, email, password):
        if password != 'correct':
            raise ValueError('no')
        return 'secret-provider-token', 'admin-sub'

    def verify(self, token):
        return 'admin-sub'


class Service:
    def summary(self):
        return {'available': 2, 'bank_rate_satang': 3450}

    def list_users(self, query=''):
        return [{'id': 1, 'username': '<script>alert(1)</script>', 'balance_units': 30000000}]


def client():
    settings = SimpleNamespace(supabase_url='https://example.supabase.co',
        supabase_publishable_key='public', web_admin_subjects=frozenset({'admin-sub'}),
        public_base_url='https://testserver', owner_id=1, session_secret='a' * 40,
        allowed_hosts=('testserver',))
    service = Mock(wraps=Service())
    service.get_user = Mock(return_value={'balance_units': 30000000})
    service.list_emails = Mock(return_value=[{'id': 1, 'email': 'a@example.org', 'status': 'available'}])
    service.preview_import = Mock(return_value={'valid': ['a@example.org'], 'invalid': 0, 'duplicates': 0})
    service.import_emails = Mock(return_value={'added': 1, 'duplicate': 0, 'invalid': 0})
    for method in ('list_orders', 'list_topups', 'list_audit', 'list_payments'):
        setattr(service, method, Mock(return_value=[{'id': 'example', 'status': 'pending'}]))
    service.expire_topups = Mock(return_value=0)
    service.history = Mock(return_value={'ledger': []})
    service.get_price = Mock(return_value=30000000)
    service.get_bank_rate_satang = Mock(return_value=3450)
    for method in ('adjust_credit', 'delete_email', 'set_price', 'set_bank_rate', 'refund_order', 'review_payment'):
        setattr(service, method, Mock(return_value={}))
    service.delete_emails = Mock(return_value={'deleted': 1})
    c = TestClient(create_app(service, settings, Auth()), base_url='https://testserver')
    c.service = service
    return c


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)


def login(c):
    token = csrf(c.get('/login'))
    return c.post('/login', data={'csrf': token, 'email': 'admin@example.org', 'password': 'correct'})


def test_login_session_and_escape():
    c = client()
    initial = c.get('/')
    assert initial.url.path == '/login'
    assert 'httponly' in initial.headers['set-cookie'].lower()
    assert login(c).status_code == 200
    assert 'secret-provider-token' not in str(c.cookies)
    assert '&lt;script&gt;' in c.get('/users').text
    assert c.get('/login').url.path == '/'


def test_missing_csrf_and_nonadmin_are_rejected():
    c = client()
    assert c.post('/login', data={'email': 'x', 'password': 'correct'}).status_code == 403
    login(c)
    assert c.post('/logout').status_code == 403
    c.app.state.settings.web_admin_subjects = frozenset()
    assert c.get('/').url.path == '/login'


def test_login_failure_is_generic():
    c = client()
    response = c.post('/login', data={'csrf': csrf(c.get('/login')), 'email': 'x', 'password': 'bad'})
    assert response.status_code == 401
    assert 'secret-provider-token' not in response.text


def test_pages_credit_preview_confirm_and_logout():
    c = client()
    login(c)
    for path in ('/', '/users', '/inventory', '/orders', '/topups', '/audit', '/settings', '/users/1/history'):
        assert c.get(path).status_code == 200
    assert 'โอนธนาคาร: 1 credit = 34.50 บาท' in c.get('/').text
    settings = c.get('/settings').text
    assert 'อัตราเติมเงินธนาคารปัจจุบัน 34.50 บาท / credit' in settings
    token = csrf(c.get('/users'))
    response = c.post('/credit/preview', data={'csrf': token, 'user_id': '1', 'amount': '0.5', 'mode': 'delta', 'reason': 'แก้ยอด'})
    assert response.status_code == 200
    key = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    response = c.post('/credit/confirm', data={'csrf': token, 'user_id': 1, 'old': 30000000, 'target': 80000000, 'reason': 'แก้ยอด', 'key': key})
    assert response.status_code == 200
    c.service.adjust_credit.assert_called_once_with('web:admin-sub', 1, target_units=80000000,
        expected_balance_units=30000000, reason='แก้ยอด', request_key='web:' + key)
    assert c.post('/logout', data={'csrf': token}).url.path == '/login'
    assert c.get('/users').url.path == '/login'


def test_order_and_topup_tables_format_fixed_point_units():
    c = client()
    login(c)
    c.service.list_orders.return_value = [{
        'price_units': 30_000_000, 'total_units': 60_000_000,
        'balance_units': 100_000_000,
    }]
    c.service.list_topups.return_value = [{
        'base_units': 500_000_000, 'expected_units': 500_950_000,
    }]

    orders = c.get('/orders').text
    topups = c.get('/topups').text

    assert '0.3 credit' in orders
    assert '0.6 credit' in orders
    assert '1 credit' in orders
    assert '5 USDT' in topups
    assert '5.0095 USDT' in topups


def test_audit_table_localizes_details_and_thai_timestamp_safely():
    c = client()
    login(c)
    c.service.list_audit.return_value = [{
        'id': 1, 'actor_id': '639', 'action': 'adjust_credit',
        'details': {'user_id': 6047343762, 'delta_units': 30000000,
                    'reason': '<script>alert(1)</script>'},
        'created_at': '2026-10-21T20:30:00+00:00',
    }]

    page = c.get('/audit').text

    assert 'ปรับเครดิต' in page
    assert '22/10/2026 03:30:00' in page
    assert '0.3 credit' in page
    assert '30000000' not in page
    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page

    c.service.list_audit.return_value = [{
        'id': 2, 'actor_id': '639', 'action': 'delete_emails',
        'details': {'email_ids': [11, 12], 'deleted': 2, 'reason': 'ล้างข้อมูลซ้ำ'},
        'created_at': '2026-10-21T20:30:00+00:00',
    }]
    deleted_page = c.get('/audit').text
    assert 'ลบอีเมลหลายรายการ' in deleted_page
    assert 'ลบสำเร็จ 2 รายการ' in deleted_page
    assert 'รหัสอีเมล 11, 12' in deleted_page


def test_dashboard_shows_successful_topup_count_instead_of_pending():
    c = client()
    login(c)
    c.service.summary.return_value = {'successful_topups': 8}

    page = c.get('/').text

    assert 'เติมเงินสำเร็จ (ครั้ง)' in page
    assert '>8<' in page
    assert 'รายการรอเติมเงิน' not in page


def test_topup_status_and_timestamps_are_readable_in_thai():
    c = client()
    login(c)
    c.service.list_topups.return_value = [{
        'id': 'request-1', 'user_id': 7, 'base_units': 500000000,
        'expected_units': 500950000, 'status': 'expired',
        'created_at': '2026-10-21T20:30:00+00:00',
        'expires_at': '2026-10-21T20:38:00+00:00',
    }]

    page = c.get('/topups').text

    assert 'หมดเวลา' in page
    assert '22/10/2026 03:30:00' in page
    assert '22/10/2026 03:38:00' in page


def test_settings_and_user_history_show_thai_times():
    c = client()
    login(c)
    c.service.list_payments.return_value = [{
        'transaction_id': 'tx-1', 'amount_units': 100000000,
        'status': 'paid', 'occurred_at': '2026-10-21T20:30:00Z',
    }]
    c.service.history.return_value = {'orders': [], 'ledger': [{
        'id': 1, 'created_at': '2026-10-21T20:30:00+00:00', 'delta_units': 30000000,
    }], 'topups': []}

    payments = c.get('/settings').text
    history = c.get('/users/1/history').text

    assert '22/10/2026 03:30:00 น. (เวลาไทย)' in payments
    assert '22/10/2026 03:30:00 น. (เวลาไทย)' in history
    assert '<pre>' not in payments
    assert '<pre>' not in history


def test_import_upload_preview_and_delete():
    c = client()
    login(c)
    token = csrf(c.get('/inventory'))
    response = c.post('/inventory/preview', data={'csrf': token}, files={'file': ('emails.txt', b'1. a@example.org|secret-password', 'text/plain')})
    assert response.status_code == 200
    assert 'secret-password' not in response.text
    assert c.post('/inventory/import', data={'csrf': token, 'emails': 'a@example.org'}).status_code == 200
    assert c.post('/inventory/delete-preview', data={'csrf': token, 'email_id': '1'}).status_code == 200
    assert c.post('/inventory/delete', data={'csrf': token, 'email_id': '1', 'reason': 'duplicate'}).status_code == 200
    c.service.delete_email.assert_called_once_with('web:admin-sub', 1, 'duplicate')
    assert c.post('/inventory/preview', data={'csrf': token}, files={'file': ('file.exe', b'abc')}).status_code == 400
    assert c.post('/inventory/preview', data={'csrf': token}, files={'file': ('file.txt', b'\xff')}).status_code == 400
    assert c.post('/inventory/preview', data={'csrf': token}, files={'file': ('file.txt', b'x' * 262145)}).status_code == 400


@pytest.mark.parametrize('action', ['price', 'refund', 'review', 'bank_rate'])
def test_management_confirm(action):
    c = client()
    login(c)
    token = csrf(c.get('/settings'))
    data = {'csrf': token, 'action': action, 'reason': 'verified by owner', 'price': '0.3', 'bank_rate': '34.50',
        'order_id': 'o1', 'transaction_id': 't1', 'user_id': '1'}
    response = c.post('/manage/preview', data=data)
    assert response.status_code == 200
    data['key'] = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    data['signature'] = re.search(r'name="signature" value="([^"]+)"', response.text).group(1)
    assert c.post('/manage/confirm', data=data).status_code == 200
    getattr(c.service, {'price': 'set_price', 'bank_rate': 'set_bank_rate',
        'refund': 'refund_order', 'review': 'review_payment'}[action]).assert_called_once()
    if action == 'bank_rate':
        c.service.set_bank_rate.assert_called_once_with('web:admin-sub', 3450, 'verified by owner')


@pytest.mark.parametrize('value', ['0', '-1', '34.501', 'NaN', '10000001'])
def test_management_rejects_invalid_bank_rate(value):
    c = client()
    login(c)
    token = csrf(c.get('/settings'))
    data = {'csrf': token, 'action': 'bank_rate', 'reason': 'verified by owner', 'bank_rate': value}
    response = c.post('/manage/preview', data=data)
    assert response.status_code == 200
    data['key'] = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    data['signature'] = re.search(r'name="signature" value="([^"]+)"', response.text).group(1)
    assert c.post('/manage/confirm', data=data).status_code == 400
    c.service.set_bank_rate.assert_not_called()


def test_management_rejects_bank_rate_changed_after_preview():
    c = client()
    login(c)
    token = csrf(c.get('/settings'))
    data = {'csrf': token, 'action': 'bank_rate', 'reason': 'verified by owner', 'bank_rate': '34.50'}
    response = c.post('/manage/preview', data=data)
    data['key'] = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    data['signature'] = re.search(r'name="signature" value="([^"]+)"', response.text).group(1)
    data['bank_rate'] = '1.00'
    assert c.post('/manage/confirm', data=data).status_code == 400
    c.service.set_bank_rate.assert_not_called()


def test_management_signature_keeps_fields_unambiguous_with_null_bytes():
    c = client()
    login(c)
    token = csrf(c.get('/settings'))
    data = {'csrf': token, 'action': 'bank_rate', 'reason': 'verified by owner',
        'bank_rate': '34.50\x00x', 'order_id': 'y'}
    response = c.post('/manage/preview', data=data)
    assert response.status_code == 200
    data['key'] = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    data['signature'] = re.search(r'name="signature" value="([^"]+)"', response.text).group(1)
    data['bank_rate'] = '34.50'
    data['order_id'] = 'x\x00y'
    assert c.post('/manage/confirm', data=data).status_code == 400
    c.service.set_bank_rate.assert_not_called()


def test_management_signature_rejects_values_extended_past_signed_limit():
    c = client()
    login(c)
    token = csrf(c.get('/settings'))
    prefix = '0' * 30 + '34'
    data = {'csrf': token, 'action': 'bank_rate', 'reason': 'verified by owner', 'bank_rate': prefix}
    response = c.post('/manage/preview', data=data)
    assert response.status_code == 200
    data['key'] = re.search(r'name="key" value="([^"]+)"', response.text).group(1)
    data['signature'] = re.search(r'name="signature" value="([^"]+)"', response.text).group(1)
    data['bank_rate'] = prefix + '50'
    assert c.post('/manage/confirm', data=data).status_code == 400
    c.service.set_bank_rate.assert_not_called()


def test_input_failures_and_login_limit():
    c = client()
    login(c)
    token = csrf(c.get('/users'))
    for value in ('NaN', 'Infinity', '0.000000001', 'garbage', '-1'):
        response = c.post('/credit/preview', data={'csrf': token, 'user_id': '1', 'amount': value, 'reason': 'test'})
        assert response.status_code == 400
    assert c.get('/inventory?status=bad').status_code == 400
    assert c.post('/inventory/delete', data={'csrf': token, 'email_id': '1', 'reason': 'x'}).status_code == 400
    assert c.post('/credit/confirm', data={'csrf': token}).status_code == 400
    assert c.post('/manage/preview', data={'csrf': token, 'action': 'wrong'}).status_code == 400
    assert c.post('/manage/confirm', data={'csrf': token}).status_code == 400
    assert c.post('/login', content=b'x' * 300001).status_code == 413
    for _ in range(6):
        response = c.post('/login', data={'csrf': token, 'email': 'a', 'password': 'bad'})
    assert response.status_code == 429


def test_provider_revocation_and_business_failure():
    from team_mail_bot.core import DomainError
    c = client()
    login(c)
    token = csrf(c.get('/users'))
    c.service.adjust_credit.side_effect = DomainError('private-sensitive-value')
    response = c.post('/credit/confirm', data={'csrf': token, 'user_id': '1', 'target': '1', 'old': '1', 'reason': 'test', 'key': 'request-unique-key-123456'})
    assert response.status_code == 400
    assert 'private-sensitive-value' not in response.text
    for key, value in c.app.state.sessions.items():
        if value.subject:
            c.app.state.sessions[key] = type(value)(value.csrf, 0, value.token, value.subject)
    assert c.get('/').url.path == '/login'


def test_supabase_auth_http_protocol(monkeypatch):
    import httpx

    from team_mail_bot.admin_web import SupabaseAuth
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith('/token'):
            return httpx.Response(200, json={'access_token': 'provider-token', 'user': {'id': 'subject'}})
        return httpx.Response(200, json={'id': 'subject'})

    real_client = httpx.Client
    monkeypatch.setattr('team_mail_bot.admin_web.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    auth = SupabaseAuth(SimpleNamespace(supabase_url='https://example.supabase.co/', supabase_publishable_key='public'))
    assert auth.login('admin@example.org', 'password') == ('provider-token', 'subject')
    assert auth.verify('provider-token') == 'subject'
    assert seen[0].url.query == b'grant_type=password'
    assert seen[1].headers['authorization'] == 'Bearer provider-token'
    assert seen[0].headers['apikey'] == 'public'


def test_real_core_web_roundtrip():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from team_mail_bot.core import AppService
    from team_mail_bot.models import Base
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    service = AppService(sessionmaker(engine))
    service.ensure_user(1, 'User')
    service.import_emails(1, 'a@example.org\nb@example.org')
    service.adjust_credit(1, 1, target_units=100000000, reason='setup', request_key='setup')
    c = client()
    c = TestClient(create_app(service, c.app.state.settings, Auth()), base_url='https://testserver')
    login(c)
    for path in ('/', '/inventory', '/users', '/orders', '/topups', '/audit', '/settings', '/users/1/history'):
        assert c.get(path).status_code == 200
    token = csrf(c.get('/inventory'))
    response = c.post('/inventory/preview', data={'csrf': token, 'emails': '1. c@example.org|hidden-password'})
    assert 'hidden-password' not in response.text
    assert 'c@example.org' in response.text
    assert c.post('/inventory/import', data={'csrf': token, 'emails': 'c@example.org'}).status_code == 200
    email_id = service.list_emails()[0]['id']
    assert c.post('/inventory/delete', data={'csrf': token, 'email_id': email_id, 'reason': 'test removal'}).status_code == 200
    assert service.list_emails(status='deleted')[0]['id'] == email_id
    assert c.post('/credit/confirm', data={'csrf': token, 'user_id': '1', 'target': 200000000, 'old': 100000000, 'reason': 'admin adjustment', 'key': 'long-unique-key-1234'}).status_code == 200
    assert service.get_user(1)['balance_units'] == 200000000
    assert c.post('/credit/confirm', data={'csrf': token, 'user_id': '1', 'target': 300000000, 'old': 100000000, 'reason': 'stale adjustment', 'key': 'long-unique-key-5678'}).status_code == 400
    assert service.list_audit()[0]['actor_id'] == 'web:admin-sub'
    engine.dispose()


def test_login_page_reuses_session_and_rate_limits_requests():
    c = client()
    token = csrf(c.get('/login'))
    cookie = c.cookies['admin_session']
    for _ in range(29):
        response = c.get('/login')
        assert response.status_code == 200
        assert csrf(response) == token
        assert 'set-cookie' not in response.headers
    assert c.cookies['admin_session'] == cookie
    assert len(c.app.state.sessions) == 1
    assert c.get('/login').status_code == 429


def test_short_window_activity_does_not_reset_login_attempt_limit(monkeypatch):
    clock = Mock(return_value=1000.0)
    monkeypatch.setattr('team_mail_bot.admin_web.time', SimpleNamespace(time=clock))
    c = client()
    token = csrf(c.get('/login'))
    data = {'csrf': token, 'email': 'admin@example.org', 'password': 'bad'}
    for _ in range(5):
        assert c.post('/login', data=data).status_code == 401
    assert c.post('/login', data=data).status_code == 429

    clock.return_value = 1061.0
    assert c.get('/login').status_code == 200
    assert c.post('/login', data=data).status_code == 429

    clock.return_value = 1300.0
    assert c.post('/login', data=data).status_code == 401


def test_full_session_store_evicts_only_oldest_anonymous():
    import time

    from team_mail_bot.admin_web import Session
    c = client()
    now = time.time()
    protected = Session('csrf', now + 1800, 'token', 'admin-sub')
    c.app.state.sessions = {'authenticated': protected, **{
        'anon-' + str(i): Session('csrf', now + 10 + i) for i in range(1999)}}
    response = c.get('/login')
    assert response.status_code == 200
    assert len(c.app.state.sessions) == 2000
    assert c.app.state.sessions['authenticated'] is protected
    assert 'anon-0' not in c.app.state.sessions
    assert 'anon-1' in c.app.state.sessions


def test_provider_and_mutation_calls_do_not_block_event_loop():
    import threading
    recorded = {}
    service = Mock(wraps=Service())

    def get_user(user_id):
        recorded['db'] = threading.get_ident()
        return {'balance_units': 30000000}

    service.get_user = get_user

    class TracedAuth(Auth):
        def login(self, email, password):
            recorded['login'] = threading.get_ident()
            return super().login(email, password)

        def verify(self, token):
            recorded['verify'] = threading.get_ident()
            return super().verify(token)

    app = create_app(service, client().app.state.settings, TracedAuth())

    @app.middleware('http')
    async def capture_loop(request, call_next):
        recorded['loop'] = threading.get_ident()
        return await call_next(request)

    c = TestClient(app, base_url='https://testserver')
    login(c)
    assert recorded['login'] != recorded['loop']
    token = csrf(c.get('/users'))
    result = c.post('/credit/preview', data={'csrf': token, 'user_id': 1, 'amount': '1', 'reason': 'test'})
    assert result.status_code == 200
    assert recorded['verify'] != recorded['loop']
    assert recorded['db'] != recorded['loop']


def test_bulk_delete_permissions_preview_and_input_validation():
    c = client()
    assert c.post('/inventory/bulk-confirm', data={'email_id': 1, 'reason': 'test'}).status_code == 401
    login(c)
    token = csrf(c.get('/inventory'))
    assert c.post('/inventory/bulk-confirm', data={'email_id': 1, 'reason': 'test'}).status_code == 403
    response = c.post('/inventory/bulk-preview', data={'csrf': token, 'email_id': ['1', '1']})
    assert response.status_code == 200
    assert 'a@example.org' in response.text
    assert c.post('/inventory/bulk-confirm', data={'csrf': token, 'email_id': ['1', '1'], 'reason': 'batch cleanup'}).status_code == 200
    c.service.delete_emails.assert_called_once_with('web:admin-sub', [1], 'batch cleanup')
    for ids in ([], ['x'], ['0'], ['-1'], [str(2**64)], ['1'] * 501):
        response = c.post('/inventory/bulk-preview', data={'csrf': token, 'email_id': ids})
        assert response.status_code == 400
    assert c.post('/inventory/bulk-preview', data={'csrf': token, 'email_id': ['2']}).status_code == 400
    assert c.post('/inventory/bulk-confirm', data={'csrf': token, 'email_id': ['1'], 'reason': 'x'}).status_code == 400


def test_real_bulk_delete_replay_has_no_partial_mutation():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from team_mail_bot.core import AppService
    from team_mail_bot.models import Base
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    service = AppService(sessionmaker(engine))
    service.import_emails(1, 'a@example.org\nb@example.org\nc@example.org')
    settings = client().app.state.settings
    c = TestClient(create_app(service, settings, Auth()), base_url='https://testserver')
    login(c)
    token = csrf(c.get('/inventory'))
    ids = [str(row['id']) for row in service.list_emails()]
    assert c.post('/inventory/bulk-confirm', data={'csrf': token, 'email_id': ids[:2], 'reason': 'bulk removal'}).status_code == 200
    # A stale request containing one deleted and one available ID fails atomically.
    assert c.post('/inventory/bulk-confirm', data={'csrf': token, 'email_id': ids[1:], 'reason': 'stale removal'}).status_code == 400
    assert len(service.list_emails()) == 1
    assert len(service.list_emails(status='deleted')) == 2
    engine.dispose()
