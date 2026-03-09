from pathlib import Path

from assistant_ops.config import Settings
from assistant_ops.integrations import configure_google_keychain
from assistant_ops.google_auth import build_google_authorization_url


def test_google_settings_are_loaded_from_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASSISTANT_OPS_GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("ASSISTANT_OPS_GOOGLE_OAUTH_PORT", "9999")

    settings = Settings.for_workspace(tmp_path)

    assert settings.google_client_id == "client-id"
    assert settings.google_oauth_port == 9999


def test_google_settings_prefer_local_config(tmp_path: Path) -> None:
    configure_google_keychain(
        tmp_path,
        client_id="configured-client-id",
        oauth_port=8123,
        client_secret_service="assistant-ops.google",
        client_secret_account="client-secret",
        refresh_token_service="assistant-ops.google",
        refresh_token_account="refresh-token",
    )

    settings = Settings.for_workspace(tmp_path)

    assert settings.google_client_id == "configured-client-id"
    assert settings.google_oauth_port == 8123
    assert settings.google_client_secret_service == "assistant-ops.google"
    assert settings.google_client_secret_account == "client-secret"


def test_build_google_authorization_url_contains_required_fields() -> None:
    url = build_google_authorization_url(
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8765/callback",
        scopes=(
            "scope-a",
            "scope-b",
        ),
        state="test-state",
    )

    assert "client_id=client-id" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback" in url
    assert "scope=scope-a+scope-b" in url
    assert "state=test-state" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
