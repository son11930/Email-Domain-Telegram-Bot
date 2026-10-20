import pytest

from team_mail_bot.cli import main


def test_cli_help_describes_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(['--help'])
    assert exc.value.code == 0
    assert 'init-db' in capsys.readouterr().out


def test_cli_invalid_environment_does_not_leak_password(monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///super-secret')
    assert main(['init-db']) == 2
    assert 'super-secret' not in capsys.readouterr().err


def test_driver_value_error_is_not_reflected_to_console(monkeypatch, capsys):
    from team_mail_bot import cli
    from team_mail_bot.config import Settings
    monkeypatch.setattr(cli.Settings, 'from_env', classmethod(
        lambda cls: Settings(database_url='postgresql+psycopg://u:p@db.example/db')))
    def fail(settings):
        raise ValueError('provider-credential-that-must-not-leak')
    monkeypatch.setattr(cli, 'build_service', fail)
    assert cli.main(['init-db']) != 0
    assert 'provider-credential-that-must-not-leak' not in capsys.readouterr().err
