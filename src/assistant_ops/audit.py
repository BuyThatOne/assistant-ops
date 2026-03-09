from __future__ import annotations

import json
from pathlib import Path

from assistant_ops.models import AuditRecord


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()

    def record(self, entry: AuditRecord) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json())
            handle.write("\n")

    def list_recent(self, limit: int = 20) -> list[AuditRecord]:
        with self._path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]

        records = [AuditRecord.model_validate(json.loads(line)) for line in lines]
        return records[-limit:][::-1]
