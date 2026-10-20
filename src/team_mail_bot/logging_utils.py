"""Redact third-party transport messages, including formatted tracebacks."""
import logging
import re
from urllib.parse import quote, unquote, urlparse


class RedactingFormatter(logging.Formatter):
    def __init__(self, settings):
        super().__init__('%(asctime)s %(levelname)s %(name)s %(message)s')
        fields = ('telegram_bot_token', 'binance_api_key', 'binance_api_secret',
                  'database_url', 'session_secret', 'supabase_publishable_key',
                  'discord_topup_webhook_url', 'discord_order_webhook_url')
        values = [getattr(settings, name, '') for name in fields]
        password = urlparse(getattr(settings, 'database_url', '')).password
        if password:
            values.extend((password, unquote(password)))
        self._secrets = tuple(sorted({candidate for value in values if value
                                     for candidate in (value, quote(value, safe=''))},
                                    key=len, reverse=True))

    def format(self, record):
        rendered = super().format(record)
        for secret in self._secrets:
            rendered = rendered.replace(secret, '[REDACTED]')
        rendered = re.sub(r'(signature=)[^&\s\x27\x22]+', r'\1[REDACTED]', rendered)
        rendered = re.sub(r'/bot\d+:[A-Za-z0-9_-]+', '/bot[REDACTED]', rendered)
        return re.sub(r'(/api/webhooks/)[^\s\x27\x22?]+', r'\1[REDACTED]', rendered)


def protect_logs(settings):
    formatter = RedactingFormatter(settings)
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(formatter)
    # Library-created handlers must not bypass the root redaction formatter.
    for name in ('aiogram', 'httpx', 'httpcore', 'uvicorn', 'uvicorn.error', 'uvicorn.access'):
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            handler.setFormatter(formatter)
