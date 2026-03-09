from pathlib import Path
import json

from assistant_ops.bootstrap import initialize_workspace
from assistant_ops.config import Settings
from assistant_ops.server import _build_google_client, build_server


def test_server_registers_expected_tools(tmp_path: Path) -> None:
    server = build_server(Path(tmp_path))

    tool_names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001

    assert "create_approval_request" in tool_names
    assert "list_email_threads" in tool_names
    assert "send_email" in tool_names
    assert "download_statement" in tool_names
    assert "list_cibc_accounts" in tool_names
    assert "get_cibc_account_balance" in tool_names
    assert "list_cibc_statements" in tool_names
    assert "download_cibc_statement" in tool_names
    assert "open_cibc_login" in tool_names
    assert "auto_sign_in_cibc" in tool_names
    assert "open_cibc_my_documents" in tool_names
    assert "open_cibc_account_statements" in tool_names
    assert "capture_cibc_session_snapshot" in tool_names
    assert "capture_cibc_account_statements_snapshot" in tool_names
    assert "list_recent_actions" in tool_names


def test_server_bootstraps_data_files(tmp_path: Path) -> None:
    build_server(Path(tmp_path))
    settings = Settings.for_workspace(Path(tmp_path))

    assert settings.email_data_path.exists()
    assert settings.calendar_data_path.exists()
    assert settings.approvals_path.exists()
    assert settings.integrations_config_path.exists()


def test_server_can_start_from_initialized_workspace(tmp_path: Path) -> None:
    initialize_workspace(Path(tmp_path))
    server = build_server(Path(tmp_path))

    tool_names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001

    assert "list_email_threads" in tool_names


def test_initialize_workspace_repairs_empty_seed_files(tmp_path: Path) -> None:
    settings = Settings.for_workspace(Path(tmp_path))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.email_data_path.write_text("", encoding="utf-8")

    initialize_workspace(Path(tmp_path))

    assert settings.email_data_path.read_text(encoding="utf-8").strip() == '{\n  "threads": [],\n  "drafts": []\n}'


def test_initialize_workspace_migrates_old_integrations_schema(tmp_path: Path) -> None:
    settings = Settings.for_workspace(Path(tmp_path))
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    settings.integrations_config_path.write_text(
        '{\n  "cibc": {\n    "card_number_ref": "legacy",\n    "password_ref": "legacy"\n  }\n}\n',
        encoding="utf-8",
    )

    initialize_workspace(Path(tmp_path))

    payload = json.loads(settings.integrations_config_path.read_text(encoding="utf-8"))
    assert payload["cibc"] == {
        "card_number_service": None,
        "card_number_account": None,
        "password_service": None,
        "password_account": None,
    }
    assert payload["google"] == {
        "client_id": None,
        "oauth_port": 8765,
        "client_secret_service": None,
        "client_secret_account": None,
        "refresh_token_service": None,
        "refresh_token_account": None,
    }


def test_build_google_client_returns_client_when_configured(tmp_path: Path, monkeypatch) -> None:
    settings = Settings.for_workspace(Path(tmp_path))
    settings = settings.model_copy(
        update={
            "google_client_id": "client-id",
            "google_client_secret_service": "assistant-ops.google",
            "google_client_secret_account": "client-secret",
            "google_refresh_token_service": "assistant-ops.google",
            "google_refresh_token_account": "refresh-token",
        }
    )

    class FakeCredentials:
        def is_available(self) -> bool:
            return True

        def read(self, *, service: str, account: str) -> str:
            if account == "client-secret":
                return "client-secret-value"
            assert service == "assistant-ops.google"
            assert account == "refresh-token"
            return "refresh-token-value"

    client = _build_google_client(settings=settings, credential_provider=FakeCredentials())

    assert client is not None
