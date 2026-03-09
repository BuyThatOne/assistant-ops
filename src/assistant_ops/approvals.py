from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from assistant_ops.models import ApprovalRequest, ApprovalStatus


class ApprovalStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._requests: dict[str, ApprovalRequest] = {}
        if self._path.exists() and self._path.read_text(encoding="utf-8").strip():
            self._load()
        elif not self._path.exists():
            self._flush()

    def create(
        self,
        *,
        action: str,
        target: str,
        reason: str | None = None,
        ttl_minutes: int = 15,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            approval_id=f"apr_{uuid4().hex}",
            action=action,
            target=target,
            reason=reason,
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        )
        self._requests[approval.approval_id] = approval
        self._flush()
        return approval

    def get(self, approval_id: str) -> ApprovalRequest | None:
        approval = self._requests.get(approval_id)
        if approval is None:
            return None
        if approval.status == ApprovalStatus.PENDING and approval.expires_at <= datetime.now(UTC):
            expired = approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self._requests[approval_id] = expired
            self._flush()
            return expired
        return approval

    def consume(self, approval_id: str, *, expected_action: str) -> ApprovalRequest:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError(f"Unknown approval id: {approval_id}")
        if approval.status == ApprovalStatus.EXPIRED:
            raise ValueError(f"Approval expired: {approval_id}")
        if approval.status == ApprovalStatus.CONSUMED:
            raise ValueError(f"Approval already consumed: {approval_id}")
        if approval.action != expected_action:
            raise ValueError(
                f"Approval action mismatch: expected {expected_action}, got {approval.action}"
            )

        consumed = approval.model_copy(update={"status": ApprovalStatus.CONSUMED})
        self._requests[approval_id] = consumed
        self._flush()
        return consumed

    def _load(self) -> None:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        self._requests = {
            item["approval_id"]: ApprovalRequest.model_validate(item)
            for item in payload.get("approvals", [])
        }

    def _flush(self) -> None:
        payload = {
            "approvals": [
                approval.model_dump(mode="json")
                for approval in self._requests.values()
            ]
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
