import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from team_mail_bot import cli
from team_mail_bot.config import Settings


def test_bot_transport_closes_when_polling_fails(monkeypatch):
    import aiogram

    import team_mail_bot.telegram_bot as telegram
    bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock()))
    dispatcher = SimpleNamespace(include_router=Mock(), start_polling=AsyncMock(side_effect=RuntimeError()))
    monkeypatch.setattr(aiogram, 'Bot', lambda token: bot)
    monkeypatch.setattr(aiogram, 'Dispatcher', lambda: dispatcher)
    monkeypatch.setattr(telegram, 'create_router', lambda service, settings: object())
    with pytest.raises(RuntimeError):
        asyncio.run(cli.run_bot(Settings(), object()))
    bot.session.close.assert_awaited_once()


def test_worker_shutdown_closes_network_clients(monkeypatch):
    import aiogram

    from team_mail_bot import payments, workers
    bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock()))
    reader, discord = SimpleNamespace(close=Mock()), SimpleNamespace(close=Mock())
    monkeypatch.setattr(aiogram, 'Bot', lambda token: bot)
    monkeypatch.setattr(payments, 'BinancePayClient', lambda *a, **kw: reader)
    monkeypatch.setattr(payments, 'PaymentPoller', lambda *a, **kw: SimpleNamespace(poll_once=Mock(return_value=0)))
    monkeypatch.setattr(workers, 'DiscordNotifier', lambda *a: discord)
    monkeypatch.setattr(workers, 'OutboxWorker', lambda *a: SimpleNamespace(run_once=AsyncMock(return_value=0)))
    async def stop(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(cli.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cli.run_worker(Settings(), object()))
    bot.session.close.assert_awaited_once()
    reader.close.assert_called_once()
    discord.close.assert_called_once()


def test_init_command_creates_schema_only_after_validation(monkeypatch, capsys):
    from team_mail_bot import db
    settings = Settings(database_url='postgresql+psycopg://u:pass@db.example/db')
    monkeypatch.setattr(cli.Settings, 'from_env', classmethod(lambda cls: settings))
    service = SimpleNamespace(factory=object())
    monkeypatch.setattr(cli, 'build_service', lambda settings: service)
    init = Mock()
    monkeypatch.setattr(db, 'init_db', init)
    assert cli.main(['init-db']) == 0
    init.assert_called_once_with(service.factory)
    assert 'initialized' in capsys.readouterr().out


def test_web_start_uses_one_worker_and_no_unredacted_server_logger(monkeypatch):
    import uvicorn

    import team_mail_bot.admin_web as web
    settings = Settings(database_url='postgresql+psycopg://u:p@db.example/db',
        supabase_url='https://project.supabase.co', supabase_publishable_key='key',
        web_admin_subjects=frozenset({'subject'}), session_secret='x' * 40)
    monkeypatch.setattr(cli.Settings, 'from_env', classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, 'build_service', lambda settings: object())
    monkeypatch.setattr(web, 'create_app', lambda *args: object())
    run = Mock()
    monkeypatch.setattr(uvicorn, 'run', run)
    assert cli.main(['web']) == 0
    assert run.call_args.kwargs['workers'] == 1
    assert run.call_args.kwargs['log_config'] is None
    assert run.call_args.kwargs['access_log'] is False
