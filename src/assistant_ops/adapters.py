from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from assistant_ops.cibc_parser import CibcSnapshotParser
from assistant_ops.cibc_session import CibcSessionManager
from assistant_ops.models import BankAccount, CalendarEvent, EmailDraft, EmailThread, StatementEntry


class EmailProvider(Protocol):
    def list_threads(self, limit: int) -> list[EmailThread]: ...
    def draft_reply(self, thread_id: str, body: str) -> EmailDraft: ...
    def send_draft(self, draft_id: str) -> EmailDraft: ...


class CalendarProvider(Protocol):
    def list_events(self, day: str) -> list[CalendarEvent]: ...
    def create_event(self, title: str, starts_at: str, ends_at: str) -> CalendarEvent: ...


class AccountingProvider(Protocol):
    def plan_statement_download(self, account_id: str, month: str, target_path: Path) -> dict[str, str]: ...


class BankingProvider(Protocol):
    def list_accounts(self) -> list[BankAccount]: ...
    def get_account(self, account_id: str) -> BankAccount: ...
    def list_statements(self, account_id: str) -> list[StatementEntry]: ...
    def plan_statement_download(self, account_id: str, month: str, target_path: Path) -> dict[str, str]: ...


class JsonEmailProvider:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() or not self._path.read_text(encoding="utf-8").strip():
            self._write(self._default_payload())

    def list_threads(self, limit: int) -> list[EmailThread]:
        payload = self._read()
        threads = [EmailThread.model_validate(item) for item in payload["threads"]]
        return threads[: max(0, limit)]

    def draft_reply(self, thread_id: str, body: str) -> EmailDraft:
        payload = self._read()
        draft = EmailDraft(draft_id=f"draft_{thread_id}", thread_id=thread_id, body=body)
        drafts = [EmailDraft.model_validate(item) for item in payload["drafts"]]
        drafts = [item for item in drafts if item.draft_id != draft.draft_id] + [draft]
        payload["drafts"] = [item.model_dump(mode="json") for item in drafts]
        self._write(payload)
        return draft

    def send_draft(self, draft_id: str) -> EmailDraft:
        payload = self._read()
        drafts = [EmailDraft.model_validate(item) for item in payload["drafts"]]
        for index, draft in enumerate(drafts):
            if draft.draft_id == draft_id:
                sent = draft.model_copy(update={"sent": True})
                drafts[index] = sent
                payload["drafts"] = [item.model_dump(mode="json") for item in drafts]
                self._write(payload)
                return sent
        raise ValueError(f"Unknown draft id: {draft_id}")

    def _read(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _default_payload(self) -> dict:
        return {
            "threads": [
                {
                    "thread_id": "thr_demo_001",
                    "subject": "Quarterly tax package",
                    "sender": "accounting@example.com",
                },
                {
                    "thread_id": "thr_demo_002",
                    "subject": "Meeting request",
                    "sender": "calendar@example.com",
                },
            ],
            "drafts": [],
        }


class JsonCalendarProvider:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() or not self._path.read_text(encoding="utf-8").strip():
            self._write(self._default_payload())

    def list_events(self, day: str) -> list[CalendarEvent]:
        payload = self._read()
        events = [CalendarEvent.model_validate(item) for item in payload["events"]]
        return [event for event in events if event.starts_at.startswith(day)]

    def create_event(self, title: str, starts_at: str, ends_at: str) -> CalendarEvent:
        payload = self._read()
        event = CalendarEvent(
            event_id=f"evt_{len(payload['events']) + 1:03d}",
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        payload["events"].append(event.model_dump(mode="json"))
        self._write(payload)
        return event

    def _read(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _default_payload(self) -> dict:
        return {
            "events": [
                {
                    "event_id": "evt_demo_001",
                    "title": "Bookkeeping review",
                    "starts_at": "2026-03-09T09:00:00-05:00",
                    "ends_at": "2026-03-09T09:30:00-05:00",
                }
            ]
        }


class FileAccountingProvider:
    def plan_statement_download(self, account_id: str, month: str, target_path: Path) -> dict[str, str]:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        return {
            "account_id": account_id,
            "month": month,
            "target_path": str(target_path),
            "status": "planned",
        }


class JsonCibcBankingProvider:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() or not self._path.read_text(encoding="utf-8").strip():
            self._write(self._default_payload())

    def list_accounts(self) -> list[BankAccount]:
        payload = self._read()
        return [BankAccount.model_validate(item) for item in payload["accounts"]]

    def get_account(self, account_id: str) -> BankAccount:
        for account in self.list_accounts():
            if account.account_id == account_id:
                return account
        raise ValueError(f"Unknown CIBC account id: {account_id}")

    def list_statements(self, account_id: str) -> list[StatementEntry]:
        return []

    def plan_statement_download(self, account_id: str, month: str, target_path: Path) -> dict[str, str]:
        account = self.get_account(account_id)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path = target_path.with_name(f"cibc_{account_id}_{month}.pdf")
        return {
            "institution": account.institution,
            "account_id": account.account_id,
            "account_type": account.account_type,
            "month": month,
            "target_path": str(target_path),
            "status": "planned",
        }

    def _read(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _default_payload(self) -> dict:
        return {
            "accounts": [
                {
                    "account_id": "cibc_chequing_001",
                    "institution": "CIBC",
                    "account_type": "chequing",
                    "currency": "CAD",
                    "balance": "2450.18",
                    "available_balance": "2400.18",
                },
                {
                    "account_id": "cibc_savings_001",
                    "institution": "CIBC",
                    "account_type": "savings",
                    "currency": "CAD",
                    "balance": "12890.44",
                    "available_balance": "12890.44",
                },
            ]
        }


class LiveCibcBankingProvider:
    def __init__(
        self,
        *,
        session_manager: CibcSessionManager,
        parser: CibcSnapshotParser,
    ) -> None:
        self._session_manager = session_manager
        self._parser = parser

    def list_accounts(self) -> list[BankAccount]:
        snapshot = self._session_manager.capture_authenticated_snapshot()
        snapshot_path = self._session_manager.resolve_snapshot_path(snapshot["snapshot_path"])
        return self._parser.parse_accounts(snapshot_path)

    def get_account(self, account_id: str) -> BankAccount:
        for account in self.list_accounts():
            if account.account_id == account_id:
                return account
        raise ValueError(f"Unknown CIBC account id: {account_id}")

    def list_statements(self, account_id: str) -> list[StatementEntry]:
        snapshot = self._session_manager.capture_authenticated_snapshot()
        snapshot_path = self._session_manager.resolve_snapshot_path(snapshot["snapshot_path"])
        return self._parser.parse_statement_entries(snapshot_path, account_id=account_id)

    def plan_statement_download(self, account_id: str, month: str, target_path: Path) -> dict[str, str]:
        account = self._account_from_id(account_id)
        statement = next((item for item in self.list_statements(account_id) if item.month == month), None)
        if statement is None:
            raise ValueError(f"No CIBC statement found for {account_id} in {month}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path = target_path.with_name(f"{account_id}_{month}.pdf")
        return {
            "institution": account.institution,
            "account_id": account.account_id,
            "account_type": account.account_type,
            "month": month,
            "statement_label": statement.label,
            "statement_route": statement.route,
            "target_path": str(target_path),
            "status": "planned-live-session",
        }

    def _account_from_id(self, account_id: str) -> BankAccount:
        parts = account_id.split("_")
        if len(parts) < 4:
            raise ValueError(f"Unsupported CIBC account id format: {account_id}")
        return BankAccount(
            account_id=account_id,
            institution="CIBC",
            account_type=parts[2].replace("-", " ").title(),
            currency="CAD",
            balance="0.00",
            available_balance=None,
        )
