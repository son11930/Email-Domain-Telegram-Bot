"""Server-rendered administration with private, short-lived server sessions."""
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .core import DomainError

UNITS = 100_000_000


class SupabaseAuth:
    def __init__(self, settings):
        self.url = settings.supabase_url.rstrip('/')
        self.key = settings.supabase_publishable_key

    def login(self, email, password):
        with httpx.Client(timeout=15) as client:
            response = client.post(self.url + '/auth/v1/token?grant_type=password',
                headers={'apikey': self.key}, json={'email': email, 'password': password})
            response.raise_for_status()
            data = response.json()
            return data['access_token'], data['user']['id']

    def verify(self, token):
        with httpx.Client(timeout=15) as client:
            response = client.get(self.url + '/auth/v1/user', headers={
                'apikey': self.key, 'Authorization': 'Bearer ' + token})
            response.raise_for_status()
            return response.json()['id']


@dataclass(frozen=True)
class Session:
    csrf: str
    expires: float
    token: str = ''
    subject: str = ''


def amount(value):
    try:
        number = Decimal(str(value))
        scaled = number * UNITS
        if not number.is_finite() or scaled != scaled.to_integral_value() or abs(number) > 1_000_000:
            raise ValueError()
        return int(scaled)
    except (InvalidOperation, ValueError, OverflowError):
        raise HTTPException(400, 'จำนวนเครดิตไม่ถูกต้อง') from None


def create_app(service, settings, auth_client=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.sessions = {}
    app.state.limits = {}
    limits_lock = Lock()
    auth = auth_client or SupabaseAuth(settings)
    templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
    templates.env.filters['credits'] = lambda n: format(Decimal(n or 0) / UNITS, 'f')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(getattr(settings, 'allowed_hosts', ('localhost', '127.0.0.1'))))

    def session(request, required=True):
        key = request.cookies.get('admin_session', '')
        current = app.state.sessions.get(key)
        if not current or current.expires < time.time():
            app.state.sessions.pop(key, None)
            if required:
                raise HTTPException(401, 'กรุณาเข้าสู่ระบบ')
            return None
        if required:
            try:
                subject = auth.verify(current.token)
            except Exception:  # noqa: BLE001 - fail closed without leaking auth provider errors.
                app.state.sessions.pop(key, None)
                raise HTTPException(401, 'กรุณาเข้าสู่ระบบใหม่') from None
            if subject != current.subject or subject not in settings.web_admin_subjects:
                app.state.sessions.pop(key, None)
                raise HTTPException(401, 'ไม่มีสิทธิ์แอดมิน')
        return current

    def limited(key, maximum=30, window=60):
        with limits_lock:
            now = time.time()
            # Each bucket retains its own expiry across endpoints with different windows.
            records = {k: v for k, v in app.state.limits.items() if v[0] > now}
            if len(records) >= 5000 and key not in records:
                raise HTTPException(429, 'กรุณาลองใหม่ภายหลัง')
            expires, count = records.get(key, (now + window, 0))
            app.state.limits = {**records, key: (expires, count + 1)}
            if count >= maximum:
                raise HTTPException(429, 'ทำรายการถี่เกินไป กรุณารอสักครู่')

    def view(request, title, **data):
        current = session(request, required=False)
        return templates.TemplateResponse(request=request, name='admin.html', context={
            'title': title, 'csrf': current.csrf if current else '',
            'authenticated': bool(current and current.subject), **data})

    def new_session(response, token='', subject=''):
        now = time.time()
        active = {k: v for k, v in app.state.sessions.items() if v.expires > now}
        if len(active) >= 2000:
            anonymous = [(key, value) for key, value in active.items() if not value.subject]
            if not anonymous:
                raise HTTPException(503, 'กรุณาลองใหม่ภายหลัง')
            oldest = min(anonymous, key=lambda pair: pair[1].expires)[0]
            active = {key: value for key, value in active.items() if key != oldest}
        key = secrets.token_urlsafe(32)
        current = Session(secrets.token_urlsafe(32), now + (1800 if token else 600), token, subject)
        app.state.sessions = {**active, key: current}
        response.set_cookie('admin_session', key, secure=settings.public_base_url.startswith('https://'),
            httponly=True, samesite='strict', max_age=1800, path='/')
        return current

    async def form(request, required=True):
        current = await asyncio.to_thread(session, request, required)
        limited(('action', request.client.host if request.client else 'unknown'), 60)
        values = await request.form(max_files=1, max_fields=520, max_part_size=262144)
        if not current or not secrets.compare_digest(str(values.get('csrf', '')), current.csrf):
            raise HTTPException(403, 'รหัสยืนยันหมดอายุ กรุณาโหลดหน้าใหม่')
        return current, values

    @app.middleware('http')
    async def security(request, call_next):
        from fastapi.responses import PlainTextResponse
        if request.method == 'POST':
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 300_000:
                    return PlainTextResponse('ไฟล์ใหญ่เกินกำหนด', status_code=413)
            request._body = bytes(data)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @app.exception_handler(HTTPException)
    async def error(request, exc):
        if exc.status_code == 401 and request.method == 'GET' and request.url.path != '/login':
            return RedirectResponse('/login', status_code=303)
        response = view(request, 'ทำรายการไม่สำเร็จ', error=exc.detail)
        response.status_code = exc.status_code
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        response = view(request, 'ทำรายการไม่สำเร็จ', error='ข้อมูลไม่ถูกต้อง ยอดเปลี่ยน หรือสถานะรายการเปลี่ยนแล้ว กรุณาตรวจสอบอีกครั้ง')
        response.status_code = 400
        return response

    @app.get('/login')
    def login_page(request: Request):
        limited(('login-page', request.client.host if request.client else 'unknown'), 30)
        existing = session(request, required=False)
        if existing and existing.subject:
            session(request)
            return RedirectResponse('/', status_code=303)
        response = view(request, 'เข้าสู่ระบบ', login=True)
        if existing:
            return response
        current = new_session(response)
        # Render again with the CSRF belonging to the newly issued anonymous session.
        rendered = templates.TemplateResponse(request=request, name='admin.html', context={
            'title': 'เข้าสู่ระบบ', 'csrf': current.csrf, 'login': True, 'authenticated': False})
        rendered.headers['set-cookie'] = response.headers['set-cookie']
        return rendered

    @app.post('/login')
    async def login_action(request: Request):
        limited(('login', request.client.host if request.client else 'unknown'), 5, 300)
        _, values = await form(request, False)
        try:
            token, subject = await asyncio.to_thread(auth.login, str(values.get('email', ''))[:254], str(values.get('password', ''))[:1024])
            if subject not in settings.web_admin_subjects:
                raise ValueError()
        except Exception:  # noqa: BLE001 - login errors must not expose upstream response contents.
            raise HTTPException(401, 'เข้าสู่ระบบไม่สำเร็จ หรือไม่มีสิทธิ์แอดมิน') from None
        app.state.sessions.pop(request.cookies.get('admin_session', ''), None)
        response = RedirectResponse('/', status_code=303)
        new_session(response, token, subject)
        return response

    @app.post('/logout')
    async def logout(request: Request):
        await form(request)
        app.state.sessions.pop(request.cookies.get('admin_session', ''), None)
        response = RedirectResponse('/login', status_code=303)
        response.delete_cookie('admin_session', path='/')
        return response

    @app.get('/')
    def dashboard(request: Request):
        session(request)
        return view(request, 'ภาพรวม', summary=service.summary())

    @app.get('/users')
    def users(request: Request, q: str = ''):
        session(request)
        return view(request, 'ผู้ใช้และเครดิต', users=service.list_users(query=q[:100]), q=q[:100])

    @app.post('/credit/preview')
    async def credit_preview(request: Request):
        _, values = await form(request)
        try:
            user_id = int(values.get('user_id', 0))
        except ValueError:
            raise HTTPException(400, 'รหัสผู้ใช้ไม่ถูกต้อง') from None
        user = await asyncio.to_thread(service.get_user, user_id)
        if not user:
            raise HTTPException(404, 'ไม่พบผู้ใช้')
        old = user['balance_units'] if isinstance(user, dict) else user.balance_units
        number = amount(values.get('amount', ''))
        target = number if values.get('mode') == 'target' else old + number
        reason = str(values.get('reason', '')).strip()
        if target < 0 or not 3 <= len(reason) <= 500:
            raise HTTPException(400, 'ยอดต้องไม่ติดลบ และระบุเหตุผลอย่างน้อย 3 ตัวอักษร')
        return view(request, 'ยืนยันปรับเครดิต', credit={'user_id': user_id, 'old': old, 'target': target,
            'reason': reason, 'key': secrets.token_urlsafe(24)})

    @app.post('/credit/confirm')
    async def credit_confirm(request: Request):
        current, values = await form(request)
        try:
            user_id, target, expected = (int(values[k]) for k in ('user_id', 'target', 'old'))
            reason = str(values.get('reason', '')).strip()
            key = str(values.get('key', ''))
            if user_id <= 0 or target < 0 or not 3 <= len(reason) <= 500 or not 16 <= len(key) <= 100:
                raise ValueError()
            await asyncio.to_thread(service.adjust_credit, 'web:' + current.subject, user_id, target_units=target,
                expected_balance_units=expected, reason=reason, request_key='web:' + key)
        except (ValueError, KeyError):
            raise HTTPException(400, 'ข้อมูลไม่ถูกต้อง หรือยอดเปลี่ยนแล้ว กรุณาตรวจสอบและยืนยันใหม่') from None
        return RedirectResponse('/users', status_code=303)

    @app.get('/inventory')
    def inventory(request: Request, status: str = 'available', q: str = ''):
        session(request)
        if status not in ('available', 'allocated', 'deleted'):
            raise HTTPException(400, 'สถานะไม่ถูกต้อง')
        return view(request, 'คลังอีเมล', inventory=service.list_emails(status=status, query=q[:100]), status=status, q=q[:100])

    @app.post('/inventory/preview')
    async def import_preview(request: Request):
        _, values = await form(request)
        text = str(values.get('emails', ''))
        upload = values.get('file')
        if upload and getattr(upload, 'filename', ''):
            raw = await upload.read(262145)
            await upload.close()
            if len(raw) > 262144 or not upload.filename.lower().endswith('.txt'):
                raise HTTPException(400, 'รับเฉพาะ .txt ไม่เกิน 256 KB')
            try:
                text += '\n' + raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise HTTPException(400, 'ไฟล์ต้องเป็น UTF-8') from None
        if len(text.encode('utf-8')) > 262144:
            raise HTTPException(400, 'ข้อมูลใหญ่เกินกำหนด')
        result = await asyncio.to_thread(service.preview_import, text)
        # Only sanitized emails are round-tripped through the confirmation page.
        emails = result['valid']
        return view(request, 'ตรวจสอบก่อนนำเข้า', imports='\n'.join(emails), import_count=len(emails),
            import_invalid=result['invalid'], import_duplicates=result['duplicates'])

    @app.post('/inventory/import')
    async def import_confirm(request: Request):
        current, values = await form(request)
        result = await asyncio.to_thread(service.import_emails, 'web:' + current.subject, str(values.get('emails', '')))
        return view(request, 'นำเข้าเรียบร้อย', import_result=result)

    @app.post('/inventory/delete-preview')
    async def delete_preview(request: Request):
        _, values = await form(request)
        return view(request, 'ยืนยันลบอีเมล', delete_id=str(values.get('email_id', ''))[:100])

    @app.post('/inventory/delete')
    async def delete_confirm(request: Request):
        current, values = await form(request)
        reason = str(values.get('reason', '')).strip()
        if not 3 <= len(reason) <= 500:
            raise HTTPException(400, 'กรุณาระบุเหตุผล 3–500 ตัวอักษร')
        try:
            email_id = int(values.get('email_id', ''))
            if email_id <= 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, 'รหัสรายการไม่ถูกต้อง') from None
        await asyncio.to_thread(service.delete_email, 'web:' + current.subject, email_id, reason)
        return RedirectResponse('/inventory', status_code=303)

    def batch_ids(values):
        raw = values.getlist('email_id')
        if not raw or len(raw) > 500:
            raise HTTPException(400, 'เลือกอีเมล 1–500 รายการ')
        try:
            ids = sorted({int(value) for value in raw})
            if any(value <= 0 or value >= 2**63 for value in ids):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(400, 'รหัสรายการไม่ถูกต้อง') from None
        return ids

    @app.post('/inventory/bulk-preview')
    async def bulk_preview(request: Request):
        _, values = await form(request)
        ids = batch_ids(values)
        available = await asyncio.to_thread(service.list_emails, status='available')
        selected = [row for row in available if row['id'] in ids]
        if len(selected) != len(ids):
            raise HTTPException(400, 'มีรายการที่ไม่พร้อมลบ กรุณาโหลดคลังใหม่')
        return view(request, 'ยืนยันลบอีเมลเป็นชุด', bulk_emails=selected)

    @app.post('/inventory/bulk-confirm')
    async def bulk_confirm(request: Request):
        current, values = await form(request)
        ids = batch_ids(values)
        reason = str(values.get('reason', '')).strip()
        if not 3 <= len(reason) <= 500:
            raise HTTPException(400, 'กรุณาระบุเหตุผล 3–500 ตัวอักษร')
        result = await asyncio.to_thread(service.delete_emails, 'web:' + current.subject, ids, reason)
        return view(request, 'ลบอีเมลเรียบร้อย', bulk_result=result)

    @app.get('/orders')
    def orders(request: Request):
        session(request)
        return view(request, 'คำสั่งซื้อ', records=service.list_orders())

    @app.get('/topups')
    def topups(request: Request):
        session(request)
        return view(request, 'รายการเติมเงิน', records=service.list_topups())

    @app.get('/audit')
    def audit(request: Request):
        session(request)
        return view(request, 'ประวัติแอดมิน', records=service.list_audit())

    @app.get('/users/{user_id}/history')
    def history(request: Request, user_id: int):
        session(request)
        records = service.history(user_id)
        return view(request, 'ประวัติผู้ใช้ ' + str(user_id), history=records)

    @app.get('/settings')
    def settings_page(request: Request):
        session(request)
        return view(request, 'จัดการรายการและราคา', settings_page=True, price=service.get_price(),
            payments=service.list_payments())

    @app.post('/manage/preview')
    async def management_preview(request: Request):
        _, values = await form(request)
        action = str(values.get('action', ''))
        reason = str(values.get('reason', '')).strip()
        if action not in ('price', 'refund', 'review') or not 3 <= len(reason) <= 500:
            raise HTTPException(400, 'ข้อมูลหรือเหตุผลไม่ถูกต้อง')
        payload = {'action': action, 'reason': reason, 'key': secrets.token_urlsafe(24)}
        for field in ('price', 'order_id', 'transaction_id', 'user_id'):
            limit = 256 if field == 'transaction_id' else 120
            payload[field] = str(values.get(field, ''))[:limit]
        return view(request, 'ยืนยันรายการสำคัญ', management=payload)

    @app.post('/manage/confirm')
    async def management_confirm(request: Request):
        current, values = await form(request)
        actor = 'web:' + current.subject
        reason = str(values.get('reason', '')).strip()
        key = str(values.get('key', ''))
        action = values.get('action')
        if not 3 <= len(reason) <= 500 or not 16 <= len(key) <= 100:
            raise HTTPException(400, 'ข้อมูลไม่ถูกต้อง')
        try:
            if action == 'price':
                price = amount(values.get('price', ''))
                if price <= 0:
                    raise ValueError()
                await asyncio.to_thread(service.set_price, actor, price, reason)
            elif action == 'refund':
                await asyncio.to_thread(service.refund_order, actor, str(values.get('order_id', ''))[:120], reason, 'web:' + key)
            elif action == 'review':
                await asyncio.to_thread(service.review_payment, actor, str(values.get('transaction_id', ''))[:256],
                    int(values.get('user_id', 0)), reason, 'web:' + key)
            else:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(400, 'ข้อมูลไม่ถูกต้อง') from None
        return RedirectResponse('/settings', status_code=303)

    return app
