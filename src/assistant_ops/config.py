from __future__ import annotations
import os
from pathlib import Path

from pydantic import BaseModel

from assistant_ops.integrations import IntegrationsConfig


class Settings(BaseModel):
    workspace_root: Path
    data_dir: Path
    config_dir: Path
    integrations_config_path: Path
    output_dir: Path
    playwright_output_dir: Path
    audit_log_path: Path
    approvals_path: Path
    email_data_path: Path
    calendar_data_path: Path
    cibc_data_path: Path
    pwcli_path: Path
    cibc_playwright_session: str
    security_path: Path
    cibc_card_number_service: str | None = None
    cibc_card_number_account: str | None = None
    cibc_password_service: str | None = None
    cibc_password_account: str | None = None

    @classmethod
    def for_workspace(cls, workspace_root: Path) -> "Settings":
        data_dir = workspace_root / "data"
        config_dir = workspace_root / "config"
        integrations_config_path = config_dir / "integrations.json"
        integrations = IntegrationsConfig.load(integrations_config_path)
        return cls(
            workspace_root=workspace_root,
            data_dir=data_dir,
            config_dir=config_dir,
            integrations_config_path=integrations_config_path,
            output_dir=workspace_root / "output",
            playwright_output_dir=workspace_root / "output" / "playwright",
            audit_log_path=data_dir / "audit_log.jsonl",
            approvals_path=data_dir / "approvals.json",
            email_data_path=data_dir / "email.json",
            calendar_data_path=data_dir / "calendar.json",
            cibc_data_path=data_dir / "cibc.json",
            pwcli_path=_resolve_pwcli_path(),
            cibc_playwright_session=os.getenv("ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION", "cibc-banking"),
            security_path=Path(os.getenv("ASSISTANT_OPS_SECURITY_PATH", "/usr/bin/security")),
            cibc_card_number_service=integrations.cibc.card_number_service,
            cibc_card_number_account=integrations.cibc.card_number_account,
            cibc_password_service=integrations.cibc.password_service,
            cibc_password_account=integrations.cibc.password_account,
        )


def _resolve_pwcli_path() -> Path:
    env_path = os.getenv("ASSISTANT_OPS_PWCLI_PATH")
    if env_path:
        return Path(env_path)

    bundled_wrapper = Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh"
    if bundled_wrapper.exists():
        return bundled_wrapper

    return Path("playwright-cli")
