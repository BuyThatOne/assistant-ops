from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class SecretReader(Protocol):
    def read(self, *, service: str, account: str) -> str: ...
    def is_available(self) -> bool: ...


class MacOSKeychainCredentialProvider:
    def __init__(self, *, security_path: Path) -> None:
        self._security_path = security_path

    def read(self, *, service: str, account: str) -> str:
        completed = subprocess.run(
            [
                str(self._security_path),
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def is_available(self) -> bool:
        completed = subprocess.run(
            [str(self._security_path), "help"],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0 or bool(completed.stderr)
