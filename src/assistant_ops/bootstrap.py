from __future__ import annotations

import argparse
import json
from pathlib import Path

from assistant_ops.config import Settings


def initialize_workspace(workspace_root: Path) -> list[Path]:
    settings = Settings.for_workspace(workspace_root)
    created: list[Path] = []
    for path in (
        settings.data_dir,
        settings.config_dir,
        workspace_root / "data" / "downloads",
        workspace_root / "docs",
        settings.output_dir,
        settings.playwright_output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    for file_path in (
        settings.approvals_path,
        settings.email_data_path,
        settings.calendar_data_path,
        settings.cibc_data_path,
        settings.integrations_config_path,
    ):
        if not file_path.exists() or not file_path.read_text(encoding="utf-8").strip():
            file_path.write_text(_seed_content(file_path.name), encoding="utf-8")
        elif file_path.name == "integrations.json":
            repair_integrations_config(file_path)
        created.append(file_path)
    return created


def _seed_content(file_name: str) -> str:
    if file_name == "approvals.json":
        return '{\n  "approvals": []\n}\n'
    if file_name == "email.json":
        return '{\n  "threads": [],\n  "drafts": []\n}\n'
    if file_name == "calendar.json":
        return '{\n  "events": []\n}\n'
    if file_name == "cibc.json":
        return '{\n  "accounts": []\n}\n'
    if file_name == "integrations.json":
        return (
            '{\n  "cibc": {\n    "card_number_service": null,\n    "card_number_account": null,\n'
            '    "password_service": null,\n    "password_account": null\n  }\n}\n'
        )
    return ""


def repair_integrations_config(path: Path) -> bool:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.write_text(_seed_content(path.name), encoding="utf-8")
        return True

    payload = json.loads(path.read_text(encoding="utf-8"))
    cibc = payload.get("cibc")
    if not isinstance(cibc, dict):
        path.write_text(_seed_content(path.name), encoding="utf-8")
        return True

    expected_keys = {
        "card_number_service",
        "card_number_account",
        "password_service",
        "password_account",
    }
    if expected_keys.issubset(cibc):
        return False

    payload["cibc"] = {
        "card_number_service": None,
        "card_number_account": None,
        "password_service": None,
        "password_account": None,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the assistant ops workspace.")
    parser.add_argument("--workspace", default=".", help="Workspace root to initialize.")
    args = parser.parse_args()
    created = initialize_workspace(Path(args.workspace).resolve())
    for path in created:
        print(path)


if __name__ == "__main__":
    main()
