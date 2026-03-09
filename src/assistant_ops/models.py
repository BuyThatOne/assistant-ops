from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ActionRisk(StrEnum):
    READ = "read"
    WRITE = "write"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    approval_id: str
    action: str
    target: str
    reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    actor: str = "local-operator"
    tool_name: str
    action_target: str
    risk: ActionRisk
    approval_required: bool
    approval_id: str | None = None
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class EmailThread(BaseModel):
    thread_id: str
    subject: str
    sender: str


class CalendarEvent(BaseModel):
    event_id: str
    title: str
    starts_at: str
    ends_at: str


class EmailDraft(BaseModel):
    draft_id: str
    thread_id: str
    body: str
    sent: bool = False


class BankAccount(BaseModel):
    account_id: str
    institution: str
    account_type: str
    currency: str
    balance: str
    available_balance: str | None = None


class StatementEntry(BaseModel):
    account_id: str
    label: str
    month: str
    route: str | None = None
