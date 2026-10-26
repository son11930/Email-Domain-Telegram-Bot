"""Durable delivery adapters; external failures never undo committed money."""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BufferedInputFile

LOG = logging.getLogger(__name__)


def credits(units: int) -> str:
    return format(Decimal(units) / 100_000_000, 'f')

def discord_user(data: dict) -> str:
    name = data.get('user_name')
    name = ' '.join(name.split())[:80] if isinstance(name, str) else ''
    return f"{name or 'ไม่ระบุชื่อ'} (ID {data.get('user_id', '')})"


def split_email_lines(emails: list[str], limit: int = 4000) -> list[str]:
    parts, lines, size = [], [], 0
    for email in emails:
        if len(email) > limit or '\n' in email or '\r' in email:
            raise ValueError('Invalid email delivery data')
        if lines and size + 1 + len(email) > limit:
            parts.append('\n'.join(lines))
            lines, size = [], 0
        size += len(email) + bool(lines)
        lines.append(email)
    if lines:
        parts.append('\n'.join(lines))
    return parts


class DeliveryError(Exception):
    def __init__(self, message: str, retry_seconds: int = 30):
        super().__init__(message)
        self.retry_seconds = retry_seconds


class DiscordNotifier:
    def __init__(self, topup_url: str, order_url: str, *, client=None):
        for url in (topup_url, order_url):
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'discord.com'
                    or not parsed.path.startswith('/api/webhooks/')
                    or parsed.username or parsed.password or parsed.query or parsed.fragment):
                raise ValueError('Invalid Discord webhook configuration')
        self.urls = {'discord_topup': topup_url, 'discord_order': order_url}
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)

    def send(self, topic: str, data: dict) -> None:
        if topic not in self.urls:
            raise DeliveryError('Unknown Discord event')
        if topic == 'discord_topup':
            text = (f"เติมเครดิตสำเร็จ | {discord_user(data)}\n"
                    f"รายการ: {data.get('topup_id', '')}\n"
                    f"รับ {credits(data.get('amount_units', 0))} USDT\n"
                    f"เพิ่ม {credits(data.get('amount_units', 0))} credit\n"
                    f"ยอดเหลือ {credits(data.get('balance_units', 0))} credit")
        else:
            statuses = {'success': 'สำเร็จ', 'failed': 'ไม่สำเร็จ',
                        'refunded': 'ยกเลิก / คืนเครดิต'}
            status = statuses.get(data.get('status'), 'ไม่ระบุ')
            text = (f"ซื้อเมล | {discord_user(data)}\n"
                    f"รายการ: {data.get('order_id', '')}\n"
                    f"จำนวน {data.get('quantity', 0)} เมล\n"
                    f"หัก {credits(data.get('total_units', 0))} credit\n"
                    f"ยอดเหลือ {credits(data.get('balance_units', 0))} credit\n"
                    f"สถานะ: {status}")
            if data.get('failure_reason'):
                text += f"\nรายละเอียด: {data['failure_reason']}"
        try:
            response = self.client.post(self.urls[topic], params={'wait': 'true'},
                json={'content': text[:1900], 'allowed_mentions': {'parse': []}})
        except httpx.HTTPError:
            raise DeliveryError('Discord unavailable') from None
        if response.status_code == 429:
            try:
                delay = max(1, min(3600, int(float(response.json().get('retry_after', 30)) + 0.999)))
            except (ValueError, TypeError):
                delay = 30
            raise DeliveryError('Discord rate limited', delay)
        if not response.is_success:
            raise DeliveryError('Discord delivery failed')

    def close(self) -> None:
        self.client.close()


class OutboxWorker:
    def __init__(self, service, bot, discord):
        self.service, self.bot, self.discord = service, bot, discord

    async def _classify_legacy_text_job(self, job: dict) -> dict:
        data = job['payload']
        if job['topic'] != 'telegram_text' or data.get('delivery_kind'):
            return job
        order = await asyncio.to_thread(self.service.get_order, data['user_id'], data['order_id'])
        email_parts = split_email_lines(order['emails'])
        if data.get('text') in email_parts:
            metadata = {'delivery_kind': 'email',
                        'email_count': len(data['text'].splitlines())}
        else:
            metadata = {'delivery_kind': 'summary'}
        return {**job, 'payload': {**data, **metadata}}

    async def _expand_order(self, job: dict) -> None:
        data = job['payload']
        order = await asyncio.to_thread(self.service.get_order, data['user_id'], data['order_id'])
        is_resend = (data.get('delivery_mode') == 'resend'
                     or job.get('dedupe_key', '').startswith('resend:'))
        if (is_resend and order.get('status') != 'delivered'
                or not is_resend and order.get('status') in ('refunded', 'failed', 'partial_failed')):
            return
        prefix = f"delivery:{job['id']}:"
        base = {'user_id': data['user_id'], 'order_id': data['order_id'],
                'delivery_mode': 'resend' if is_resend else 'initial',
                'refund_eligible': not is_resend}
        if len(order['emails']) > 1:
            await asyncio.to_thread(self.service.enqueue, 'telegram_document',
                {**base, 'emails': order['emails']}, prefix + 'file')
        for index, part in enumerate(split_email_lines(order['emails'])):
            email_count = len(part.splitlines())
            await asyncio.to_thread(self.service.enqueue, 'telegram_text',
                {**base, 'delivery_kind': 'email', 'email_count': email_count, 'text': part},
                prefix + f'text:{index}')
        summary = (f"✅ รายการ {order['id']}\n"
                   f"หัก {credits(order['total_units'])} credit\n"
                   f"ยอดเหลือหลังรายการ {credits(order['balance_units'])} credit")
        await asyncio.to_thread(self.service.enqueue, 'telegram_text',
            {**base, 'delivery_kind': 'summary', 'text': summary}, prefix + 'summary')

    async def _deliver(self, job: dict) -> None:
        topic, data = job['topic'], job['payload']
        if topic in {'telegram_text', 'telegram_document'}:
            order = await asyncio.to_thread(self.service.get_order, data['user_id'], data['order_id'])
            if order.get('status') == 'refunded':
                return
        if topic == 'telegram_order':
            await self._expand_order(job)
        elif topic == 'telegram_document':
            document = BufferedInputFile(('\n'.join(data['emails']) + '\n').encode('utf-8'),
                                         filename=f"order_{data['order_id']}.txt")
            await self.bot.send_document(chat_id=data['user_id'], document=document)
        elif topic == 'telegram_text':
            await self.bot.send_message(chat_id=data['user_id'], text=data['text'], parse_mode=None)
        elif topic == 'telegram_delivery_failure':
            refund = credits(data['refund_units'])
            balance = credits(data['balance_units'])
            count = data['failed_emails']
            if data.get('refund_applied') and data.get('review_required'):
                text = (f"⚠️ รายการ {data['order_id']} ส่งเมลไม่สำเร็จ {count} รายการ\n"
                        f"คืนเครดิตที่ยืนยันได้ {refund} credit แล้ว\n"
                        'ยังมีส่วนที่ต้องตรวจสอบ กรุณาติดต่อแอดมิน\n'
                        f"ยอดคงเหลือ {balance} credit")
            elif data.get('refund_applied'):
                text = (f"❌ รายการ {data['order_id']} ส่งเมลไม่สำเร็จ {count} รายการ\n"
                        f"คืนเครดิต {refund} credit แล้ว\n"
                        f"ยอดคงเหลือ {balance} credit\n"
                        'เครดิตส่วนที่ส่งไม่สำเร็จคืนแล้ว หากต้องการเมลเพิ่มเติมสามารถสั่งใหม่ได้')
            elif data.get('review_required'):
                text = (f"⚠️ รายการ {data['order_id']} ส่งเมลไม่สำเร็จ {count} รายการ\n"
                        'ยังไม่ได้คืนเครดิตอัตโนมัติ กรุณาติดต่อแอดมินเพื่อตรวจสอบ\n'
                        f"ยอดคงเหลือ {balance} credit")
            else:
                text = (f"⚠️ ส่งซ้ำรายการ {data['order_id']} ไม่สำเร็จ {count} รายการ\n"
                        'เครดิตไม่มีการเปลี่ยนแปลง\n'
                        f"ยอดคงเหลือ {balance} credit")
            await self.bot.send_message(chat_id=data['user_id'], text=text, parse_mode=None)
        elif topic == 'telegram_topup':
            text = (f"✅ เติมเครดิตสำเร็จ\nรายการ {data['topup_id']}\n"
                    f"เพิ่ม {credits(data['amount_units'])} credit\n"
                    f"ยอดเหลือหลังรายการ {credits(data['balance_units'])} credit")
            await self.bot.send_message(chat_id=data['user_id'], text=text, parse_mode=None)
        elif topic in {'discord_order', 'discord_topup'}:
            await asyncio.to_thread(self.discord.send, topic, data)
        else:
            raise DeliveryError('Unknown outbox topic', 3600)

    async def run_once(self) -> int:
        # Claim just before delivery, rather than letting a serial batch's later
        # messages expire while preceding network requests are still in flight.
        jobs = await asyncio.to_thread(self.service.claim_outbox, limit=1)
        for job in jobs:
            try:
                job = await self._classify_legacy_text_job(job)
                await self._deliver(job)
            except Exception as exc:  # noqa: BLE001 - persist only safe error class and retry.
                # Never persist transport exceptions: Telegram tokens, webhook URLs
                # and signed Binance queries may appear in their string form.
                delay = getattr(exc, 'retry_seconds', getattr(exc, 'retry_after',
                    min(3600, 2 ** min(job['attempts'], 10) * 5)))
                await asyncio.to_thread(self.service.finish_outbox, job['id'], False,
                                        error=type(exc).__name__, retry_seconds=int(delay),
                                        lease_token=job.get('lease_token'),
                                        delivery_kind=job['payload'].get('delivery_kind', ''),
                                        email_count=job['payload'].get('email_count'),
                                        refund_eligible=job['payload'].get('refund_eligible'),
                                        permanent_failure=isinstance(
                                            exc, (TelegramBadRequest, TelegramForbiddenError)))
                LOG.warning('Outbox delivery deferred: %s', type(exc).__name__)
            else:
                await asyncio.to_thread(self.service.finish_outbox, job['id'], True,
                                        lease_token=job.get('lease_token'),
                                        delivery_kind=job['payload'].get('delivery_kind', ''),
                                        email_count=job['payload'].get('email_count'),
                                        refund_eligible=job['payload'].get('refund_eligible'))
        return len(jobs)
