"""Process entry points. No service starts until its configuration validates."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

from dotenv import load_dotenv

from .config import Settings

LOG = logging.getLogger(__name__)


def build_service(settings):
    from .core import AppService
    from .db import create_session_factory
    return AppService(create_session_factory(settings.database_url),
        price_units=settings.price_units, precision=settings.topup_precision,
        topup_ttl_seconds=settings.topup_ttl_seconds,
        max_order_quantity=settings.max_order_quantity, admin_ids=settings.admin_ids)


async def run_bot(settings, service):
    from aiogram import Bot, Dispatcher

    from .slipok import SlipOKClient
    from .telegram_bot import create_router
    bot = Bot(settings.telegram_bot_token)
    slipok = (SlipOKClient(settings.slipok_api_key, settings.slipok_branch_id)
              if settings.slipok_configured else None)
    dispatcher = Dispatcher()
    router = create_router(service, settings, slipok) if slipok else create_router(service, settings)
    dispatcher.include_router(router)
    try:
        await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        await bot.session.close()
        if slipok is not None:
            slipok.close()


async def run_worker(settings, service):
    from aiogram import Bot

    from .payments import BinancePayClient, PaymentPoller
    from .workers import DiscordNotifier, OutboxWorker
    bot = Bot(settings.telegram_bot_token)
    reader = BinancePayClient(settings.binance_api_key, settings.binance_api_secret,
                              settings.binance_receiver_id, base_url=settings.binance_base_url)
    poller = PaymentPoller(reader, service, lookback_seconds=settings.payment_lookback_seconds)
    discord = DiscordNotifier(settings.discord_topup_webhook_url, settings.discord_order_webhook_url)
    deliveries = OutboxWorker(service, bot, discord)

    async def payments_loop():
        while True:
            started = time.monotonic()
            try:
                await asyncio.to_thread(service.expire_topups)
                await asyncio.to_thread(service.expire_bank_topups)
                count = await asyncio.to_thread(poller.poll_once)
                LOG.info('Payment reconciliation completed: %d events', count)
            except Exception as exc:  # noqa: BLE001 - isolate failures and redact provider details.
                LOG.warning('Payment reconciliation deferred: %s', type(exc).__name__)
            await asyncio.sleep(max(1, settings.poll_seconds - (time.monotonic() - started)))

    async def delivery_loop():
        while True:
            try:
                count = await deliveries.run_once()
            except Exception as exc:  # noqa: BLE001 - durable jobs remain retryable after outages.
                LOG.warning('Outbox unavailable: %s', type(exc).__name__)
                count = 0
            await asyncio.sleep(0 if count else settings.outbox_poll_seconds)

    try:
        await asyncio.gather(payments_loop(), delivery_loop())
    finally:
        await bot.session.close()
        reader.close()
        discord.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Telegram email wallet and admin panel')
    parser.add_argument('command', choices=('init-db', 'bot', 'worker', 'web'))
    args = parser.parse_args(argv)
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    # HTTP request logs contain bearer endpoints and signed payment queries.
    for name in ('httpx', 'httpcore', 'aiogram.event'):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        settings = Settings.from_env()
        settings.validate(args.command)
    except ValueError as exc:
        # Our configuration validator emits only static field descriptions.
        print(f'Configuration error: {exc}', file=sys.stderr)
        return 2
    try:
        from .logging_utils import protect_logs
        protect_logs(settings)
        service = build_service(settings)
        if args.command == 'init-db':
            from .db import init_db
            init_db(service.factory)
            print('Database schema initialized; application API roles denied by default.')
        elif args.command == 'bot':
            asyncio.run(run_bot(settings, service))
        elif args.command == 'worker':
            asyncio.run(run_worker(settings, service))
        else:
            import uvicorn

            from .admin_web import create_app
            uvicorn.run(create_app(service, settings), host=os.getenv('WEB_HOST', '127.0.0.1'),
                        port=settings.port, workers=1, access_log=False, log_config=None)
    except KeyboardInterrupt:
        return 0
    except ValueError:
        # Driver/library ValueError messages can contain raw connection details.
        print('Startup configuration is invalid; check .env.example and field formats.', file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - startup must not print credentials from driver errors.
        print(f'Startup failed ({type(exc).__name__}); check configuration and connectivity.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
