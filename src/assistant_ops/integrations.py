from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel


class CibcIntegrationConfig(BaseModel):
    card_number_service: str | None = None
    card_number_account: str | None = None
    password_service: str | None = None
    password_account: str | None = None


class GoogleIntegrationConfig(BaseModel):
    client_id: str | None = None
    oauth_port: int | None = None
    client_secret_service: str | None = None
    client_secret_account: str | None = None
    refresh_token_service: str | None = None
    refresh_token_account: str | None = None


class IntegrationsConfig(BaseModel):
    cibc: CibcIntegrationConfig = CibcIntegrationConfig()
    google: GoogleIntegrationConfig = GoogleIntegrationConfig()

    @classmethod
    def load(cls, path: Path) -> "IntegrationsConfig":
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return cls()
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


def configure_cibc_keychain(
    workspace_root: Path,
    *,
    card_number_service: str,
    card_number_account: str,
    password_service: str,
    password_account: str,
) -> Path:
    path = workspace_root / "config" / "integrations.json"
    config = IntegrationsConfig.load(path)
    config.cibc = CibcIntegrationConfig(
        card_number_service=card_number_service,
        card_number_account=card_number_account,
        password_service=password_service,
        password_account=password_account,
    )
    config.save(path)
    return path


def configure_google_keychain(
    workspace_root: Path,
    *,
    client_id: str,
    oauth_port: int,
    client_secret_service: str,
    client_secret_account: str,
    refresh_token_service: str,
    refresh_token_account: str,
) -> Path:
    path = workspace_root / "config" / "integrations.json"
    config = IntegrationsConfig.load(path)
    config.google = GoogleIntegrationConfig(
        client_id=client_id,
        oauth_port=oauth_port,
        client_secret_service=client_secret_service,
        client_secret_account=client_secret_account,
        refresh_token_service=refresh_token_service,
        refresh_token_account=refresh_token_account,
    )
    config.save(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure macOS Keychain integration identifiers.")
    parser.add_argument("--workspace", default=".", help="Workspace root to configure.")
    parser.add_argument("--cibc-card-number-service", required=True, help="Keychain service name for the CIBC card number.")
    parser.add_argument("--cibc-card-number-account", required=True, help="Keychain account name for the CIBC card number.")
    parser.add_argument("--cibc-password-service", required=True, help="Keychain service name for the CIBC password.")
    parser.add_argument("--cibc-password-account", required=True, help="Keychain account name for the CIBC password.")
    args = parser.parse_args()

    path = configure_cibc_keychain(
        Path(args.workspace).resolve(),
        card_number_service=args.cibc_card_number_service,
        card_number_account=args.cibc_card_number_account,
        password_service=args.cibc_password_service,
        password_account=args.cibc_password_account,
    )
    print(path)


def google_main() -> None:
    parser = argparse.ArgumentParser(description="Configure Google OAuth integration identifiers.")
    parser.add_argument("--workspace", default=".", help="Workspace root to configure.")
    parser.add_argument("--google-client-id", required=True, help="Google OAuth client ID.")
    parser.add_argument("--google-oauth-port", type=int, default=8765, help="Loopback OAuth callback port.")
    parser.add_argument("--google-client-secret-service", required=True, help="Keychain service name for the Google OAuth client secret.")
    parser.add_argument("--google-client-secret-account", required=True, help="Keychain account name for the Google OAuth client secret.")
    parser.add_argument("--google-refresh-token-service", required=True, help="Keychain service name for the Google refresh token.")
    parser.add_argument("--google-refresh-token-account", required=True, help="Keychain account name for the Google refresh token.")
    args = parser.parse_args()

    path = configure_google_keychain(
        Path(args.workspace).resolve(),
        client_id=args.google_client_id,
        oauth_port=args.google_oauth_port,
        client_secret_service=args.google_client_secret_service,
        client_secret_account=args.google_client_secret_account,
        refresh_token_service=args.google_refresh_token_service,
        refresh_token_account=args.google_refresh_token_account,
    )
    print(path)
