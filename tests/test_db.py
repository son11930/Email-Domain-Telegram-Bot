"""Schema setup must not commit unprotected PostgreSQL tables."""
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

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
