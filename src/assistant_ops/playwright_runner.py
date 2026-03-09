from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Protocol


class CommandRunner(Protocol):
    def run(self, args: list[str], cwd: Path) -> str: ...


class SubprocessCommandRunner:
    def run(self, args: list[str], cwd: Path) -> str:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()


class PlaywrightCli:
    def __init__(
        self,
        *,
        pwcli_path: Path,
        workspace_root: Path,
        session_name: str | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self._pwcli_path = pwcli_path
        self._workspace_root = workspace_root
        self._session_name = session_name
        self._runner = runner or SubprocessCommandRunner()

    def open(self, url: str, *, headed: bool = True) -> str:
        args = self._base_args() + ["open", url]
        if headed:
            args.append("--headed")
        return self._runner.run(args, self._workspace_root)

    def goto(self, url: str) -> str:
        return self._runner.run(self._base_args() + ["goto", url], self._workspace_root)

    def snapshot(self) -> dict[str, str]:
        output = self._runner.run(self._base_args() + ["snapshot"], self._workspace_root)
        match = re.search(r"\[Snapshot\]\((?P<path>[^)]+)\)", output)
        snapshot_path = match.group("path") if match else ""
        return {"output": output, "snapshot_path": snapshot_path}

    def click(self, ref: str) -> str:
        return self._runner.run(self._base_args() + ["click", ref], self._workspace_root)

    def fill(self, ref: str, value: str) -> str:
        return self._runner.run(self._base_args() + ["fill", ref, value], self._workspace_root)

    def state_save(self, path: Path) -> str:
        return self._runner.run(self._base_args() + ["state-save", str(path)], self._workspace_root)

    def _base_args(self) -> list[str]:
        args = [str(self._pwcli_path)]
        if self._session_name:
            args.extend(["--session", self._session_name])
        return args
