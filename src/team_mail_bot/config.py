"""Validated environment settings; credentials are deliberately omitted from repr."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse


def _integer(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(env.get(name, str(default)))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {name}") from None
    if value < minimum:
        raise ValueError(f"Invalid {name}")
    return value


def _ids(raw: str) -> frozenset[int]:
    try:
        values = frozenset(int(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError:
        raise ValueError("Invalid ADMIN_IDS") from None
    if any(value <= 0 for value in values):
        raise ValueError("Invalid ADMIN_IDS")
    return values


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default="", repr=False)
    telegram_bot_token: str = field(default="", repr=False)
    owner_id: int = 0
    admin_ids: frozenset[int] = frozenset()
    binance_api_key: str = field(default="", repr=False)
    binance_api_secret: str = field(default="", repr=False)
    binance_receiver_id: str = ""
    binance_base_url: str = "https://api.binance.com"
    supabase_url: str = ""
    supabase_publishable_key: str = field(default="", repr=False)
    web_admin_subjects: frozenset[str] = frozenset()
    session_secret: str = field(default="", repr=False)
    public_base_url: str = "http://localhost:8001"
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    discord_topup_webhook_url: str = field(default="", repr=False)
    discord_order_webhook_url: str = field(default="", repr=False)
    price_units: int = 30_000_000
    topup_precision: int = 4
    topup_ttl_seconds: int = 480
    max_order_quantity: int = 1000
    poll_seconds: int = 30
    payment_lookback_seconds: int = 86400
    outbox_poll_seconds: int = 2
    port: int = 8001

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        owner_id = _integer(env, "OWNER_ID", 0, minimum=0)
        admins = _ids(env.get("ADMIN_IDS", "")) | ({owner_id} if owner_id else set())
        precision = _integer(env, "TOPUP_PRECISION", 4)
        if precision not in {3, 4}:
            raise ValueError("TOPUP_PRECISION must be 3 or 4")
        try:
            price = Decimal(env.get("PRICE_CREDITS", "0.30"))
            scaled = price * 100_000_000
            if not price.is_finite() or price <= 0 or scaled != scaled.to_integral_value():
                raise ValueError()
            price_units = int(scaled)
        except (InvalidOperation, ValueError, OverflowError):
            raise ValueError("Invalid PRICE_CREDITS") from None
        public_url = env.get("PUBLIC_BASE_URL", "http://localhost:8001").rstrip("/")
        parsed = urlparse(public_url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("PUBLIC_BASE_URL requires HTTPS")
        binance_url = env.get("BINANCE_BASE_URL", "https://api.binance.com").rstrip("/")
        if binance_url not in {"https://api.binance.com"}:
            raise ValueError("BINANCE_BASE_URL must be the official API origin")
        return cls(
            database_url=env.get("DATABASE_URL", ""),
            telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
            owner_id=owner_id, admin_ids=frozenset(admins),
            binance_api_key=env.get("BINANCE_API_KEY", ""),
            binance_api_secret=env.get("BINANCE_API_SECRET", ""),
            binance_receiver_id=env.get("BINANCE_RECEIVER_ID", ""),
            binance_base_url=binance_url,
            supabase_url=env.get("SUPABASE_URL", "").rstrip("/"),
            supabase_publishable_key=env.get("SUPABASE_PUBLISHABLE_KEY", ""),
            web_admin_subjects=frozenset(v.strip() for v in env.get("WEB_ADMIN_SUBJECTS", "").split(",") if v.strip()),
            session_secret=env.get("SESSION_SECRET", ""),
            public_base_url=public_url,
            allowed_hosts=tuple(v.strip() for v in env.get("ALLOWED_HOSTS", parsed.hostname or "localhost").split(",") if v.strip()),
            discord_topup_webhook_url=env.get("DISCORD_TOPUP_WEBHOOK_URL", ""),
            discord_order_webhook_url=env.get("DISCORD_ORDER_WEBHOOK_URL", ""),
            price_units=price_units, topup_precision=precision,
            topup_ttl_seconds=_integer(env, "TOPUP_TTL_SECONDS", 480),
            max_order_quantity=_integer(env, "MAX_ORDER_QUANTITY", 1000),
            poll_seconds=_integer(env, "POLL_SECONDS", 30),
            payment_lookback_seconds=_integer(env, "PAYMENT_LOOKBACK_SECONDS", 86400),
            outbox_poll_seconds=_integer(env, "OUTBOX_POLL_SECONDS", 2),
            port=_integer(env, "PORT", 8001),
        )

    def validate(self, command: str) -> None:
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use external PostgreSQL")
        required = {
            "bot": (self.telegram_bot_token, self.owner_id),
            "worker": (self.telegram_bot_token, self.binance_api_key, self.binance_api_secret,
                       self.binance_receiver_id, self.discord_order_webhook_url,
                       self.discord_topup_webhook_url),
            "web": (self.supabase_url, self.supabase_publishable_key,
                    self.web_admin_subjects, self.session_secret),
        }
        if not all(required.get(command, (True,))):
            raise ValueError(f"Missing configuration for {command}; see .env.example")
        if command == "web" and len(self.session_secret) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 random characters")
        if self.supabase_url and urlparse(self.supabase_url).scheme != "https":
            raise ValueError("SUPABASE_URL requires HTTPS")
