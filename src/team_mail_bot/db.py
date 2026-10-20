"""SQLAlchemy sessions; PostgreSQL in production, SQLite for isolated tests."""
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def create_session_factory(database_url):
    options = {'pool_pre_ping': True}
    database_url = make_url(database_url)
    if database_url.drivername in ('postgres', 'postgresql'):
        database_url = database_url.set(drivername='postgresql+psycopg')
    is_sqlite = database_url.get_backend_name() == 'sqlite'
    if is_sqlite:
        options.update(connect_args={'check_same_thread': False}, poolclass=StaticPool)
    engine = create_engine(database_url, **options)
    if is_sqlite:
        @event.listens_for(engine, 'connect')
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
    return sessionmaker(engine, expire_on_commit=False)

def init_db(factory):
    engine = factory.kw['bind']
    Base.metadata.create_all(engine)
    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            roles = set(connection.scalars(text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")))
            for table in Base.metadata.sorted_tables:
                name = engine.dialect.identifier_preparer.quote(table.name)
                connection.execute(text(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY'))
                connection.execute(text(f'REVOKE ALL ON TABLE {name} FROM PUBLIC'))
                for role in roles:
                    quoted_role = engine.dialect.identifier_preparer.quote(role)
                    connection.execute(text(f'REVOKE ALL ON TABLE {name} FROM {quoted_role}'))
