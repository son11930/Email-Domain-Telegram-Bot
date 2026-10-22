"""Thai private-chat interface. All financial mutations belong to AppService."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
from io import BytesIO
from uuid import uuid4
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .core import DomainError
from .slipok import MAX_IMAGE_BYTES, SlipOKError

LOG = logging.getLogger(__name__)
UNITS = 100_000_000
MAX_UPLOAD = 512_000

class BoundedBytesIO(BytesIO):
    """Reject Telegram downloads that exceed the image memory budget."""
    def write(self, data):
        if self.tell() + len(data) > MAX_UPLOAD:
            raise ValueError('Slip image is too large')
        return super().write(data)


def format_units(units: int) -> str:
    return f'{Decimal(units) / UNITS:.8f}'.rstrip('0').rstrip('.') or '0'


def parse_amount(value: str, *, decimals: int = 8, signed: bool = False) -> int:
    pattern = rf'{"[+-]?" if signed else ""}\d{{1,9}}(?:\.\d{{1,{decimals}}})?'
    if not re.fullmatch(pattern, value.strip()):
        raise ValueError('กรุณาระบุจำนวนเป็นตัวเลขทศนิยมตามที่กำหนด')
    try:
        amount = Decimal(value.strip())
        result = int(amount * UNITS)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError('จำนวนไม่ถูกต้อง') from exc
    if not signed and result <= 0:
        raise ValueError('จำนวนต้องมากกว่า 0')
    return result


def keyboard(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
        for row in rows
    ])


def main_menu(user_id: int, price: int, admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [(f'⚡ ขอ 1 เมลด่วน — {format_units(price)} credit',
          f'q:{user_id}:{price}:{uuid4().hex[:16]}')],
        [('📩 ซื้อหลายเมล', 'bulk'), ('💰 เติมเครดิต', 'topup')],
        [('💳 ยอดคงเหลือ', 'balance'), ('📦 คลังเมล', 'stock')],
        [('📋 ประวัติ / ส่งเมลซ้ำ', 'history')],
    ]
    if admin:
        rows += [[('🛠 จัดการสำหรับแอดมิน', 'admin:menu')]]
    return keyboard(*rows)


class UserRateLimit:
    """Fixed memory budget; idle users are evicted, no permanent ID registry."""
    def __init__(self, capacity: int = 4096, interval: float = 0.5):
        self.capacity = capacity
        self.interval = interval
        self.entries: OrderedDict[int, float] = OrderedDict()

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        previous = self.entries.pop(user_id, None)
        self.entries[user_id] = now
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)
        return previous is None or now - previous >= self.interval


class ChatGuard(BaseMiddleware):
    def __init__(self):
        self.limiter = UserRateLimit()

    async def __call__(self, handler, event, data):
        message = event.message if isinstance(event, CallbackQuery) else event
        if not message or message.chat.type != 'private' or not event.from_user:
            if isinstance(event, CallbackQuery):
                await event.answer('กรุณาใช้ในแชทส่วนตัว', show_alert=True)
            return None
        if not self.limiter.allow(event.from_user.id):
            if isinstance(event, CallbackQuery):
                await event.answer('กรุณารอสักครู่แล้วลองอีกครั้ง')
            return None
        return await handler(event, data)


class TelegramController:
    def __init__(self, service, settings, slipok=None):
        self.service = service
        self.settings = settings
        self.slipok = slipok

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.settings.owner_id or user_id in self.settings.admin_ids

    async def call(self, method: str, *args, **kwargs):
        return await asyncio.to_thread(getattr(self.service, method), *args, **kwargs)

    async def say(self, message, text: str, markup=None):
        await message.answer(text, reply_markup=markup, parse_mode=None)

    async def menu(self, message, user_id):
        user = await self.call('get_user', user_id)
        price = await self.call('get_price')
        name = user.get('name')
        name = ' '.join(name.split())[:80] if isinstance(name, str) else ''
        text = (f'📩 Nethinat Mail Service\nชื่อ: {escape(name or "ไม่ระบุชื่อ")}\n'
                f'รหัสผู้ใช้ (แตะค้างเพื่อคัดลอก): <code>{user_id}</code>\n'
                f'ยอดคงเหลือ: {format_units(user["balance_units"])} credit\n'
                f'ราคา: {format_units(price)} credit / เมล')
        await message.answer(text, reply_markup=main_menu(
            user_id, price, self.is_admin(user_id)), parse_mode='HTML')

    async def message(self, message: Message, state):
        if message.chat.type != 'private' or not message.from_user:
            return
        user_id = message.from_user.id
        text = (message.text or '').strip()
        try:
            await self.call('ensure_user', user_id, message.from_user.full_name)
            if text.split('@')[0] in ('/start', '/menu', '/cancel'):
                current = await state.get_state()
                data = await state.get_data()
                if current == 'bank_slip' and data.get('bank_topup_id'):
                    await self.call('cancel_bank_topup', user_id, data['bank_topup_id'])
                await state.clear()
                return await self.menu(message, user_id)
            current = await state.get_state()
            if current and current.startswith('admin_') and not self.is_admin(user_id):
                await state.clear()
                return await self.say(message, 'เฉพาะแอดมินเท่านั้น')
            if current == 'bulk':
                return await self.bulk_preview(message, state, text, user_id)
            if current == 'topup':
                amount = parse_amount(text, decimals=2)
                return await self.topup(message, user_id, amount, state)
            if current == 'bank_topup_amount':
                amount = parse_amount(text, decimals=2)
                return await self.bank_topup(message, user_id, amount // 1_000_000, state)
            if current == 'bank_slip':
                return await self.verify_bank_slip(message, user_id, state)
            if current == 'admin_import':
                return await self.import_preview(message, state)
            if current == 'admin_credit':
                return await self.credit_preview(message, state, text)
            if current == 'admin_credit_amount':
                return await self.credit_amount_preview(message, state, text)
            if current == 'admin_delete':
                return await self.delete_preview(message, state, text)
            await self.say(message, 'ใช้ /start เพื่อเปิดเมนู หรือ /cancel เพื่อยกเลิก')
        except Exception as exc:  # noqa: BLE001 - boundary sanitizes provider / DB errors.
            await self.report(message, exc)

    async def report(self, message, exc):
        # Never reflect arbitrary exception messages (can contain passwords / DSNs).
        if isinstance(exc, ValueError):
            text = 'ข้อมูลไม่ถูกต้อง กรุณาตรวจจำนวน รูปแบบ และขนาดข้อมูล แล้วลองใหม่'
        elif isinstance(exc, DomainError):
            text = str(exc)
        else:
            LOG.error('Telegram action failed (%s)', type(exc).__name__)
            text = 'ระบบขัดข้องชั่วคราว กรุณาลองใหม่ภายหลัง การซื้อที่สำเร็จดูได้ในประวัติ'
        await self.say(message, text)

    async def callback(self, callback: CallbackQuery, state):
        message = callback.message
        if not message or message.chat.type != 'private':
            return await callback.answer('ใช้ในแชทส่วนตัวเท่านั้น', show_alert=True)
        user_id = callback.from_user.id
        action = callback.data or ''
        await callback.answer()
        try:
            if action.startswith(('admin:', 'confirm:')) and not self.is_admin(user_id):
                return await self.say(message, 'เฉพาะแอดมินเท่านั้น')
            if action == 'menu':
                await state.clear()
                return await self.menu(message, user_id)
            if action.startswith('q:'):
                _, owner, price, nonce = action.split(':')
                if int(owner) != user_id or not re.fullmatch('[a-f0-9]{1,32}', nonce):
                    return await self.say(message, 'ปุ่มนี้ไม่ใช่ของคุณ กรุณาใช้ /start')
                return await self.buy(message, user_id, 1, f'tg:{user_id}:{nonce}', int(price))
            if action.startswith('buy:'):
                return await self.confirm_bulk(message, state, action, user_id)
            if action in ('bulk', 'topup'):
                await state.clear()
                await state.set_state(action)
                if action == 'bulk':
                    return await self.say(message, f'พิมพ์จำนวนเมล (1–{self.settings.max_order_quantity})')
                return await self.say(message, 'เลือกวิธีเติมเครดิต', keyboard(
                    [('Binance Pay / UID', 'method:binance'), ('โอนธนาคาร / ส่งสลิป', 'method:bank')],
                    [('ยกเลิก', 'menu')]))
            if action == 'method:binance':
                await state.clear()
                await state.set_state('topup')
                return await self.say(message, 'เลือกยอด USDT หรือพิมพ์ยอดไม่เกิน 2 ทศนิยม', keyboard(
                    [('1 USDT', 'fund:1'), ('5 USDT', 'fund:5')],
                    [('10 USDT', 'fund:10'), ('20 USDT', 'fund:20')], [('ยกเลิก', 'menu')]))
            if action == 'method:bank':
                if not getattr(self.settings, 'slipok_configured', False) or self.slipok is None:
                    return await self.say(message, 'ระบบโอนธนาคารยังตั้งค่าไม่ครบ กรุณาใช้ Binance Pay ชั่วคราว')
                await state.clear()
                await state.set_state('bank_topup_amount')
                return await self.say(message, 'พิมพ์ยอดเงินบาทที่ต้องการเติม (ขั้นต่ำ 150 บาท, ไม่เกิน 10,000 บาท)')
            if action.startswith('fund:'):
                return await self.topup(message, user_id, parse_amount(action[5:], decimals=2), state)
            if action.startswith('cancel:'):
                await self.call('cancel_topup', user_id, action[7:])
                return await self.say(message, 'ยกเลิกคำขอแล้ว หากโอนแล้วกรุณาติดต่อแอดมิน')
            if action.startswith('cancelbank:'):
                await self.call('cancel_bank_topup', user_id, action[11:])
                await state.clear()
                return await self.say(message, 'ยกเลิกคำขอแล้ว หากโอนแล้วกรุณาติดต่อเจ้าของเป็นการส่วนตัว')
            if action == 'balance':
                return await self.menu(message, user_id)
            if action == 'stock':
                available = await self.call('get_stock')
                return await self.say(message, f'📦 เมลพร้อมเบิก {available} เมล')
            if action == 'history':
                return await self.history(message, user_id)
            if action.startswith('resend:'):
                return await self.resend(message, user_id, action[7:])
            if action.startswith('admin:'):
                return await self.admin(message, state, action)
            if action.startswith('confirm:'):
                return await self.admin_confirm(message, state, action, user_id)
            await self.say(message, 'ปุ่มหมดอายุ กรุณาใช้ /start')
        except Exception as exc:  # noqa: BLE001 - boundary sanitizes provider / DB errors.
            await self.report(message, exc)

    async def bulk_preview(self, message, state, text, user_id):
        if not re.fullmatch(r'\d{1,6}', text):
            raise ValueError('quantity')
        quantity = int(text)
        if not 1 <= quantity <= self.settings.max_order_quantity:
            raise ValueError('quantity')
        price = await self.call('get_price')
        user = await self.call('get_user', user_id)
        total = quantity * price
        if total > user['balance_units']:
            return await self.say(message, 'เครดิตไม่เพียงพอ กรุณาเติมเครดิต')
        nonce = uuid4().hex[:16]
        await state.update_data(quantity=quantity, price=price, nonce=nonce)
        await self.say(message,
                       f'ซื้อ {quantity} เมล × {format_units(price)} = {format_units(total)} credit\n'
                       f'คงเหลือหลังซื้อ: {format_units(user["balance_units"] - total)} credit',
                       keyboard([('✅ ยืนยันซื้อ', f'buy:{nonce}'), ('ยกเลิก', 'menu')]))

    async def confirm_bulk(self, message, state, action, user_id):
        data = await state.get_data()
        if not data.get('nonce') or action != f'buy:{data["nonce"]}':
            return await self.say(message, 'ปุ่มหมดอายุ กรุณาเลือกรายการใหม่')
        await self.buy(message, user_id, data['quantity'], f'tg:{user_id}:{data["nonce"]}', data['price'])

    async def buy(self, message, user_id, quantity, key, price):
        order = await self.call('purchase', user_id, quantity, key,
                                expected_price_units=price, include_emails=False)
        await self.say(message, f'✅ บันทึกรายการ {order["id"]} แล้ว ระบบกำลังส่งเมล\n'
                       'ดูหรือขอส่งรายการเดิมได้ในประวัติ')
        await self.menu(message, user_id)

    async def topup(self, message, user_id, amount, state):
        request = await self.call('request_topup', user_id, amount)
        await state.clear()
        exact = format_units(request['expected_units'])
        expiry = request.get('expires_at', '')
        if expiry:
            expiry = datetime.fromisoformat(str(expiry)).astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S น. ไทย')
        await self.say(message,
                       f'💰 เติมผ่าน Binance Pay / UID\nยอดที่ต้องโอน: {exact} USDT\n'
                       f'รหัสบัญชีรับ: {self.settings.binance_receiver_id}\n'
                       f'ได้รับ: {exact} credit\nหมดอายุ: {expiry}\n'
                       'กรุณาโอนยอดตรงทุกหลัก ระบบตรวจอัตโนมัติ ไม่ต้องส่งสลิป\n'
                       'หากหมดอายุหรือยกเลิกแล้วอย่าโอนตามคำขอนี้',
                       keyboard([('ยกเลิกคำขอ', f'cancel:{request["id"]}')], [('เมนูหลัก', 'menu')]))

    async def bank_topup(self, message, user_id, base_satang, state):
        request = await self.call('create_bank_topup', user_id, base_satang)
        expected = request['expected_satang']
        expiry = datetime.fromisoformat(request['expires_at']).astimezone(
            ZoneInfo('Asia/Bangkok')).strftime('%H:%M น. เวลาไทย')
        await state.clear()
        await state.set_state('bank_slip')
        await state.update_data(bank_topup_id=request['id'])
        amount = Decimal(expected) / 100
        bank_name = f'ธนาคาร: {self.settings.bank_name}\n' if self.settings.bank_name else ''
        text = (
            f'🏦 เติมเงินผ่านบัญชีธนาคาร\n{escape(bank_name)}'
            f'ชื่อบัญชี: {escape(self.settings.bank_account_name)}\n'
            f'เลขบัญชี (แตะค้างเพื่อคัดลอก): <code>{escape(self.settings.bank_account_number)}</code>\n'
            f'ยอดที่ต้องโอน (แตะค้างเพื่อคัดลอก): <code>{amount:.2f}</code> บาท\n'
            f'ได้รับประมาณ: {format_units(request["credited_units"])} credit\n'
            f'โอนภายใน 15 นาที (ก่อน {expiry}) แล้วส่งรูปสลิปในแชทนี้\n'
            'ระบบจะตรวจสอบยอด ผู้รับ เวลา และรายการสลิปซ้ำก่อนเพิ่มเครดิต'
        )
        await message.answer(text, reply_markup=keyboard(
            [('ยกเลิกคำขอ', f'cancelbank:{request["id"]}')], [('เมนูหลัก', 'menu')]),
            parse_mode='HTML')

    async def verify_bank_slip(self, message, user_id, state):
        data = await state.get_data()
        topup_id = data.get('bank_topup_id')
        if not topup_id:
            await state.clear()
            return await self.say(message, 'ไม่พบคำขอเติมเงิน กรุณาเริ่มรายการใหม่')
        if self.slipok is None:
            return await self.say(message, 'ระบบตรวจสลิปยังไม่พร้อม กรุณาติดต่อเจ้าของเป็นการส่วนตัว')
        photo = getattr(message, 'photo', None) or []
        document = getattr(message, 'document', None)
        if photo:
            file_id = photo[-1].file_id
            declared_size = getattr(photo[-1], 'file_size', None)
            filename = 'telegram-slip.jpg'
        elif document:
            filename = getattr(document, 'file_name', '') or ''
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return await self.say(message, 'ส่งได้เฉพาะไฟล์ภาพสลิป PNG, JPG หรือ WEBP')
            file_id = document.file_id
            declared_size = getattr(document, 'file_size', None)
        else:
            return await self.say(message, 'กรุณาส่งรูปสลิปเป็นภาพหรือไฟล์ภาพ')
        if declared_size is not None and (declared_size < 12 or declared_size > MAX_IMAGE_BYTES):
            return await self.say(message, 'ไฟล์ภาพต้องมีขนาดไม่เกิน 500 KB')
        try:
            request = await self.call('get_bank_topup', user_id, topup_id)
            if request['status'] not in ('pending', 'failed'):
                return await self.say(message, 'คำขอนี้ถูกใช้หรือยกเลิกแล้ว กรุณาติดต่อเจ้าของหากโอนเงินแล้ว')
            bot_file = await message.bot.get_file(file_id)
            destination = BoundedBytesIO()
            await message.bot.download_file(bot_file.file_path, destination=destination)
            image = destination.getvalue()
            if len(image) > MAX_IMAGE_BYTES:
                return await self.say(message, 'ไฟล์ภาพต้องมีขนาดไม่เกิน 500 KB')
            verified = await asyncio.to_thread(self.slipok.verify_slip, image, filename,
                                               Decimal(request['expected_satang']) / 100)
            satang = int(verified['amount'] * 100)
            result = await self.call('complete_bank_topup', user_id, topup_id,
                                     verified['trans_ref'], satang, verified['occurred_at'])
            await state.clear()
            if result['status'] == 'paid':
                return await self.say(message, '✅ ตรวจสอบสลิปสำเร็จ เติมเครดิตเข้าบัญชีแล้ว')
            return await self.say(message, 'ตรวจสลิปได้แต่ข้อมูลไม่ตรงหรือหมดเวลา จึงยังไม่เติมเครดิต กรุณาติดต่อเจ้าของเป็นการส่วนตัว')
        except (ValueError, DomainError) as exc:
            return await self.report(message, exc)
        except SlipOKError:
            return await self.say(message, 'ตรวจสลิปไม่สำเร็จ จึงยังไม่เติมเครดิต กรุณาติดต่อเจ้าของเป็นการส่วนตัว')

    async def history(self, message, user_id):
        data = await self.call('history', user_id)
        orders = data.get('orders', [])
        lines = ['📋 ประวัติล่าสุด']
        buttons = []
        for order in orders[:10]:
            lines += [f'ซื้อ {order["id"]}: {order.get("quantity", "")} เมล']
            buttons += [[(f'ส่งซ้ำ {order["id"]}', f'resend:{order["id"]}')]]
        for entry in data.get('ledger', [])[:10]:
            lines += [f'{entry.get("kind", "เครดิต")}: {format_units(entry["delta_units"])} credit']
        await self.say(message, '\n'.join(lines) if len(lines) > 1 else 'ยังไม่มีประวัติ',
                       keyboard(*buttons, [('เมนูหลัก', 'menu')]))

    async def resend(self, message, user_id, order_id):
        order = await self.call('get_order', user_id, order_id)
        nonce = uuid4().hex
        await self.call('enqueue', 'telegram_order', {'order_id': order['id'], 'user_id': user_id},
                        f'resend:{order["id"]}:{nonce}')
        await self.say(message, 'รับคำขอส่งรายการเดิมแล้ว ไม่หักเครดิตเพิ่ม')

    async def admin(self, message, state, action):
        modes = {'admin:import': ('admin_import', ('ส่งข้อความหรือไฟล์ .txt UTF-8 ไม่เกิน 500 KB\n'
                                 'รองรับ email|password ระบบจะเก็บเฉพาะเมล ไม่ต้องส่งรหัสผ่านหากแยกแล้ว')),
                 'admin:credit': ('admin_credit', ('ส่ง Telegram ID และจำนวนเครดิต เช่น 6450298295 1.5\n'
                                  'หรือส่ง ID ก่อน แล้วค่อยส่งจำนวนเครดิต (ใส่ - เพื่อลด)')),
                 'admin:delete': ('admin_delete', 'พิมพ์: EMAIL_ID เหตุผลในการลบ\nลบได้เฉพาะเมลพร้อมขาย')}
        await state.clear()
        if action in modes:
            mode, prompt = modes[action]
            await state.set_state(mode)
            return await self.say(message, prompt)
        await self.say(message, 'จัดการระบบ (ตรวจสิทธิ์ด้วย Telegram ID)', keyboard(
            [('📥 เพิ่มเมล', 'admin:import'), ('💳 ปรับเครดิต', 'admin:credit')],
            [('🗑 ลบเมล', 'admin:delete'), ('เมนูหลัก', 'menu')]))

    async def import_preview(self, message, state):
        text = message.text or ''
        if message.document:
            doc = message.document
            if not (doc.file_name or '').lower().endswith('.txt') or not doc.file_size or doc.file_size > MAX_UPLOAD:
                raise ValueError('upload')
            stream = await message.bot.download(doc, timeout=20)
            raw = stream.read(MAX_UPLOAD + 1)
            if len(raw) > MAX_UPLOAD:
                raise ValueError('upload')
            text = raw.decode('utf-8-sig')
        if len(text.encode('utf-8')) > MAX_UPLOAD:
            raise ValueError('upload')
        preview = await self.call('preview_import', text)
        # Only validated addresses survive in transient FSM. Raw passwords are discarded.
        emails = preview['valid']
        nonce = uuid4().hex[:16]
        await state.update_data(emails=emails, nonce=nonce, operation='import')
        await self.say(message, f'นำเข้าผ่านตรวจ {len(emails)} เมล\n'
                       f'ซ้ำ: {preview.get("duplicates", 0)} / ผิดรูปแบบ: {preview.get("invalid", 0)}\n'
                       'ข้อมูลที่เก็บมีเฉพาะอีเมล',
                       keyboard([('ยืนยันเพิ่มเมล', f'confirm:{nonce}'), ('ยกเลิก', 'menu')]))

    async def credit_preview(self, message, state, text):
        parts = text.split(maxsplit=3)
        if not parts or not re.fullmatch(r'\d{1,20}', parts[0]):
            raise ValueError('credit')
        target_id = int(parts[0])
        if target_id <= 0 or target_id > 2**63 - 1:
            raise ValueError('credit user id')
        await state.clear()
        await state.set_state('admin_credit')
        if len(parts) == 1:
            await self.call('get_user', target_id)
            await state.set_state('admin_credit_amount')
            await state.update_data(credit_user_id=target_id)
            return await self.say(message, f'ผู้ใช้ {target_id}\nส่งจำนวนเครดิตที่ต้องการปรับ '
                           '(เช่น 5 เพิ่มเครดิต, -1 หักเครดิต)')
        if len(parts) == 2:
            _, amount = parts
            mode, reason = 'delta', 'ปรับเครดิตผ่าน Telegram โดยแอดมิน'
        elif len(parts) == 4 and parts[1] in ('delta', 'target'):
            _, mode, amount, reason = parts
            if not 3 <= len(reason) <= 300:
                raise ValueError('reason')
        else:
            raise ValueError('credit')
        units = parse_amount(amount, signed=mode == 'delta') if amount != '0' else 0
        if mode == 'delta' and units == 0:
            raise ValueError('zero credit adjustment')
        user = await self.call('get_user', target_id)
        await self.show_credit_confirmation(message, state, target_id, mode, units,
                                            reason, user['balance_units'])

    async def credit_amount_preview(self, message, state, text):
        data = await state.get_data()
        target_id = data.get('credit_user_id')
        if not isinstance(target_id, int) or target_id <= 0:
            await state.clear()
            return await self.say(message, 'ขั้นตอนหมดอายุ กรุณาเริ่มปรับเครดิตใหม่')
        try:
            units = parse_amount(text, signed=True)
        except ValueError:
            return await self.say(message, 'จำนวนเครดิตไม่ถูกต้อง เช่น 5 เพื่อเพิ่ม หรือ -1 เพื่อลด')
        if units == 0:
            return await self.say(message, 'จำนวนเครดิตต้องไม่เป็นศูนย์')
        user = await self.call('get_user', target_id)
        await self.show_credit_confirmation(message, state, target_id, 'delta', units,
                                            'ปรับเครดิตผ่าน Telegram โดยแอดมิน',
                                            user['balance_units'])

    async def show_credit_confirmation(self, message, state, target_id, mode, units, reason, before):
        after = units if mode == 'target' else before + units
        if after < 0:
            return await self.say(message, 'หักเครดิตไม่ได้ เพราะยอดคงเหลือจะติดลบ')
        nonce = uuid4().hex[:16]
        await state.clear()
        await state.set_state('admin_credit')
        await state.update_data(operation='credit', nonce=nonce, user_id=target_id,
                                mode=mode, units=units, reason=reason, balance=before)
        await self.say(message, f'ผู้ใช้ {target_id}\nยอดเดิม {format_units(before)} → '
                       f'{format_units(after)} credit\nเหตุผล: {reason}',
                       keyboard([('ยืนยันปรับเครดิต', f'confirm:{nonce}'), ('ยกเลิก', 'menu')]))

    async def delete_preview(self, message, state, text):
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or not 3 <= len(parts[1]) <= 300 or not parts[0].isdigit():
            raise ValueError('delete')
        nonce = uuid4().hex[:16]
        await state.update_data(operation='delete', email_id=int(parts[0]), reason=parts[1], nonce=nonce)
        await self.say(message, f'ลบเมลรหัส {parts[0]}\nเหตุผล: {parts[1]}',
                       keyboard([('ยืนยันลบ', f'confirm:{nonce}'), ('ยกเลิก', 'menu')]))

    async def admin_confirm(self, message, state, action, user_id):
        data = await state.get_data()
        if not data.get('nonce') or action != f'confirm:{data["nonce"]}':
            return await self.say(message, 'ปุ่มหมดอายุ กรุณาเริ่มใหม่')
        operation = data.get('operation')
        if operation == 'import':
            result = await self.call('import_emails', user_id, '\n'.join(data['emails']))
            await self.say(message, f'นำเข้าสำเร็จ: {result.get("imported", result.get("added", 0))} เมล')
        elif operation == 'credit':
            current = await self.call('get_user', data['user_id'])
            if current['balance_units'] != data['balance']:
                await state.clear()
                return await self.say(message, 'ยอดเปลี่ยนระหว่างยืนยัน กรุณาทำรายการใหม่')
            kwargs = {f'{data["mode"]}_units': data['units'], 'reason': data['reason'],
                      'request_key': f'tg-admin:{user_id}:{data["nonce"]}',
                      'expected_balance_units': data['balance']}
            await self.call('adjust_credit', user_id, data['user_id'], **kwargs)
            await self.say(message, 'ปรับเครดิตสำเร็จ บันทึกประวัติแล้ว')
        elif operation == 'delete':
            await self.call('delete_email', user_id, data['email_id'], data['reason'])
            await self.say(message, 'ลบเมลพร้อมขายแล้ว บันทึกประวัติแล้ว')
        await state.clear()


def create_router(service, settings, slipok=None) -> Router:
    router = Router(name='team_mail')
    controller = TelegramController(service, settings, slipok)
    guard = ChatGuard()
    router.message.outer_middleware(guard)
    router.callback_query.outer_middleware(guard)
    router.message.register(controller.message)
    router.callback_query.register(controller.callback)
    return router
