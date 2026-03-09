from pathlib import Path

from assistant_ops.config import Settings
from assistant_ops.integrations import IntegrationsConfig, configure_cibc_keychain


def test_integrations_config_loads_defaults_when_missing(tmp_path: Path) -> None:
    config = IntegrationsConfig.load(tmp_path / "missing.json")

    assert config.cibc.card_number_service is None
    assert config.cibc.card_number_account is None
    assert config.cibc.password_service is None
    assert config.cibc.password_account is None


def test_configure_cibc_keychain_writes_local_config(tmp_path: Path) -> None:
    path = configure_cibc_keychain(
        tmp_path,
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
    )

    config = IntegrationsConfig.load(path)

    assert config.cibc.card_number_service == "assistant-ops.cibc"
    assert config.cibc.card_number_account == "card-number"
    assert config.cibc.password_service == "assistant-ops.cibc"
    assert config.cibc.password_account == "password"


def test_settings_reads_keychain_config_from_local_file(tmp_path: Path) -> None:
    configure_cibc_keychain(
        tmp_path,
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
    )

    settings = Settings.for_workspace(tmp_path)

    assert settings.cibc_card_number_service == "assistant-ops.cibc"
    assert settings.cibc_card_number_account == "card-number"
    assert settings.cibc_password_service == "assistant-ops.cibc"
    assert settings.cibc_password_account == "password"
