import pytest

from team_mail_bot.config import Settings


def test_defaults_are_public_bot_and_thirty_cent_price():
    settings = Settings.from_env({})
    assert settings.price_units == 30_000_000
    assert settings.topup_precision == 4
    assert settings.outbox_poll_seconds == 2
    assert settings.admin_ids == frozenset()


def test_owner_has_admin_access_and_keys_are_not_printed():
    settings = Settings.from_env({"OWNER_ID": "123", "ADMIN_IDS": "456,789", "BINANCE_API_SECRET": "hidden-value"})
    assert settings.admin_ids == frozenset({123, 456, 789})
    assert "hidden-value" not in repr(settings)


@pytest.mark.parametrize("values", [
    {"TOPUP_PRECISION": "2"}, {"OWNER_ID": "abc"}, {"POLL_SECONDS": "0"},
    {"PRICE_CREDITS": "NaN"}, {"PRICE_CREDITS": "-1"},
    {"PUBLIC_BASE_URL": "http://example.com"},
])
def test_invalid_configuration_fails_safely(values):
    with pytest.raises(ValueError):
        Settings.from_env(values)


def test_production_database_must_be_external_postgres():
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings.from_env({"DATABASE_URL": "sqlite:///local.db"}).validate("init-db")


def test_worker_requires_real_credentials_and_discord_pair():
    settings = Settings.from_env({"DATABASE_URL": "postgresql+psycopg://user:pass@db.example/db"})
    with pytest.raises(ValueError):
        settings.validate("worker")


def test_binance_base_url_cannot_forward_keys_to_arbitrary_host():
    with pytest.raises(ValueError):
        Settings.from_env({"BINANCE_BASE_URL": "https://attacker.example"})


def test_bank_details_and_slipok_credentials_load_without_repr_leak():
    settings = Settings.from_env({
        'BANK_ACCOUNT_NAME': 'Sample Receiver',
        'BANK_ACCOUNT_NUMBER': '000-000000-0',
        'SLIPOK_API_KEY': 'private-key',
        'SLIPOK_BRANCH_ID': 'branch-123',
    })
    assert settings.bank_account_name == 'Sample Receiver'
    assert settings.bank_account_number == '000-000000-0'
    assert settings.slipok_configured
    assert 'private-key' not in repr(settings)
