"""Schema setup must not commit unprotected PostgreSQL tables."""
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from team_mail_bot.db import init_db
from team_mail_bot.models import Base


def test_postgres_schema_and_security_share_one_transaction(monkeypatch):
    engine = Mock()
    engine.dialect.name = 'postgresql'
    engine.dialect.identifier_preparer.quote.side_effect = lambda value: value
    connection = Mock()
    connection.scalars.return_value = []
    connection.execute.side_effect = RuntimeError('injected security setup failure')
    transaction = MagicMock()
    transaction.__enter__.return_value = connection
    transaction.__exit__.return_value = False
    engine.begin.return_value = transaction
    create_tables = Mock()
    monkeypatch.setattr(Base.metadata, 'create_all', create_tables)

    with pytest.raises(RuntimeError, match='injected security setup failure'):
        init_db(SimpleNamespace(kw={'bind': engine}))

    create_tables.assert_called_once_with(connection)
    engine.begin.assert_called_once_with()
    assert transaction.__exit__.call_args.args[0] is RuntimeError


def test_init_db_adds_delivery_time_and_backfills_existing_delivered_orders():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    created_at = '2026-10-20 12:34:56.000000'
    with engine.begin() as connection:
        connection.execute(text('''CREATE TABLE orders (
            id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL,
            request_key VARCHAR(160) UNIQUE NOT NULL, quantity INTEGER NOT NULL,
            price_units BIGINT NOT NULL, total_units BIGINT NOT NULL,
            balance_units BIGINT NOT NULL, status VARCHAR(20) NOT NULL,
            created_at DATETIME NOT NULL)'''))
        connection.execute(text('''INSERT INTO orders
            (id, user_id, request_key, quantity, price_units, total_units,
             balance_units, status, created_at)
            VALUES ('legacy', 7, 'legacy:request', 1, 30000000, 30000000,
                    70000000, 'delivered', :created_at)'''), {'created_at': created_at})
        connection.execute(text('''INSERT INTO orders
            (id, user_id, request_key, quantity, price_units, total_units,
             balance_units, status, created_at)
            VALUES ('legacy-refund', 7, 'legacy:refund', 1, 30000000, 30000000,
                    70000000, 'refunded', :created_at)'''), {'created_at': created_at})
    factory = sessionmaker(engine, expire_on_commit=False)

    init_db(factory)
    init_db(factory)

    assert 'delivered_at' in {column['name'] for column in inspect(engine).get_columns('orders')}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT delivered_at FROM orders WHERE id='legacy'")) == created_at
        assert connection.scalar(text("SELECT delivered_at FROM orders WHERE id='legacy-refund'")) is None
    engine.dispose()
