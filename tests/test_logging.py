import logging
import sys
from types import SimpleNamespace

from team_mail_bot.logging_utils import RedactingFormatter


def test_provider_tracebacks_and_urls_redact_credentials():
    formatter = RedactingFormatter(SimpleNamespace(telegram_bot_token='123456:MY_PRIVATE_TOKEN',
        binance_api_secret='secret-signing-key', binance_api_key='',
        database_url='postgresql://u:db-password@db.example/db', session_secret='',
        supabase_publishable_key='', discord_topup_webhook_url='', discord_order_webhook_url=''))
    try:
        raise RuntimeError('https://api.telegram.org/bot123456:MY_PRIVATE_TOKEN/sendMessage secret-signing-key '
                           'https://api.binance.com/a?signature=abc123 '
                           'https://discord.com/api/webhooks/123/hidden-webhook-token')
    except RuntimeError:
        record = logging.LogRecord('aiogram.event', logging.ERROR, '', 1, 'transport failed: %s',
                                   ('db-password',), sys.exc_info())
    text = formatter.format(record)
    for secret in ('MY_PRIVATE_TOKEN', 'secret-signing-key', 'abc123', 'hidden-webhook-token', 'db-password'):
        assert secret not in text
    assert 'RuntimeError' in text
