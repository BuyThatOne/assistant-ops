from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from assistant_ops.cibc_parser import CibcSnapshotParser
from assistant_ops.cibc_session import CibcSessionManager
from assistant_ops.google_client import GoogleApiClient, build_gmail_reply_raw
from assistant_ops.models import BankAccount, CalendarEvent, EmailDraft, EmailThread, StatementEntry


class EmailProvider(Protocol):
    def list_threads(self, limit: int) -> list[EmailThread]: ...
    def search_threads(self, query: str, limit: int) -> list[EmailThread]: ...
    def get_thread(self, thread_id: str) -> dict[str, object]: ...
    def draft_reply(self, thread_id: str, body: str) -> EmailDraft: ...
    def send_draft(self, draft_id: str) -> EmailDraft: ...


class CalendarProvider(Protocol):
    def list_events(self, day: str) -> list[CalendarEvent]: ...
    def create_event(self, title: str, starts_at: str, ends_at: str) -> CalendarEvent: ...
    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        starts_at: str | None = None,
        ends_at: str | None = None,
    ) -> CalendarEvent: ...
    def delete_event(self, event_id: str) -> None: ...


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

    def search_threads(self, query: str, limit: int) -> list[EmailThread]:
        needle = query.casefold()
        payload = self._read()
        threads = [EmailThread.model_validate(item) for item in payload["threads"]]
        matches = [
            thread
            for thread in threads
            if needle in thread.subject.casefold() or needle in thread.sender.casefold()
        ]
        return matches[: max(0, limit)]

    def get_thread(self, thread_id: str) -> dict[str, object]:
        for thread in self._read()["threads"]:
            if thread["thread_id"] == thread_id:
                return {
                    "thread_id": thread["thread_id"],
                    "subject": thread["subject"],
                    "messages": [
                        {
                            "message_id": f"{thread_id}-1",
                            "sender": thread["sender"],
                            "date": "",
                            "snippet": thread["subject"],
                        }
                    ],
                }
        raise ValueError(f"Unknown thread id: {thread_id}")

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

    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        starts_at: str | None = None,
        ends_at: str | None = None,
    ) -> CalendarEvent:
        payload = self._read()
        events = [CalendarEvent.model_validate(item) for item in payload["events"]]
        for index, event in enumerate(events):
            if event.event_id == event_id:
                updated = event.model_copy(
                    update={
                        "title": title or event.title,
                        "starts_at": starts_at or event.starts_at,
                        "ends_at": ends_at or event.ends_at,
                    }
                )
                events[index] = updated
                payload["events"] = [item.model_dump(mode="json") for item in events]
                self._write(payload)
                return updated
        raise ValueError(f"Unknown event id: {event_id}")

    def delete_event(self, event_id: str) -> None:
        payload = self._read()
        events = [CalendarEvent.model_validate(item) for item in payload["events"]]
        payload["events"] = [item.model_dump(mode="json") for item in events if item.event_id != event_id]
        self._write(payload)

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


class GoogleGmailProvider:
    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, *, client: GoogleApiClient) -> None:
        self._client = client

    def list_threads(self, limit: int) -> list[EmailThread]:
        return self.search_threads("", limit)

    def search_threads(self, query: str, limit: int) -> list[EmailThread]:
        query_param = f"&q={quote(query)}" if query else ""
        payload = self._client.request_json(
            method="GET",
            url=f"{self.BASE_URL}/threads?maxResults={max(0, limit)}{query_param}",
        )
        threads: list[EmailThread] = []
        for item in payload.get("threads", []):
            thread = self._client.request_json(
                method="GET",
                url=f"{self.BASE_URL}/threads/{item['id']}?format=metadata&metadataHeaders=Subject&metadataHeaders=From",
            )
            threads.append(self._to_email_thread(thread))
        return threads

    def get_thread(self, thread_id: str) -> dict[str, object]:
        payload = self._client.request_json(
            method="GET",
            url=(
                f"{self.BASE_URL}/threads/{thread_id}"
                "?format=full&metadataHeaders=Subject&metadataHeaders=From"
                "&metadataHeaders=To&metadataHeaders=Date"
            ),
        )
        subject = "(no subject)"
        messages: list[dict[str, str]] = []
        for message in payload.get("messages", []):
            headers = _gmail_headers(message)
            subject = headers.get("Subject", subject)
            messages.append(
                {
                    "message_id": message.get("id", ""),
                    "sender": headers.get("From", "unknown"),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": message.get("snippet", ""),
                }
            )
        return {
            "thread_id": payload["id"],
            "subject": subject,
            "messages": messages,
        }

    def draft_reply(self, thread_id: str, body: str) -> EmailDraft:
        thread = self._client.request_json(
            method="GET",
            url=(
                f"{self.BASE_URL}/threads/{thread_id}"
                "?format=metadata&metadataHeaders=Subject&metadataHeaders=From"
                "&metadataHeaders=Reply-To&metadataHeaders=Message-ID&metadataHeaders=References"
            ),
        )
        last_message = thread["messages"][-1]
        headers = _gmail_headers(last_message)
        raw = build_gmail_reply_raw(
            to_address=headers.get("Reply-To") or headers.get("From", ""),
            subject=headers.get("Subject", "(no subject)"),
            body=body,
            message_id=headers.get("Message-ID"),
            references=headers.get("References"),
        )
        payload = self._client.request_json(
            method="POST",
            url=f"{self.BASE_URL}/drafts",
            body={
                "message": {
                    "threadId": thread_id,
                    "raw": raw,
                }
            },
        )
        return EmailDraft(
            draft_id=payload["id"],
            thread_id=thread_id,
            body=body,
        )

    def send_draft(self, draft_id: str) -> EmailDraft:
        payload = self._client.request_json(
            method="POST",
            url=f"{self.BASE_URL}/drafts/send",
            body={"id": draft_id},
        )
        return EmailDraft(
            draft_id=draft_id,
            thread_id=payload.get("message", {}).get("threadId", ""),
            body="",
            sent=True,
        )

    def _to_email_thread(self, payload: dict) -> EmailThread:
        first_message = payload["messages"][0]
        headers = _gmail_headers(first_message)
        return EmailThread(
            thread_id=payload["id"],
            subject=headers.get("Subject", "(no subject)"),
            sender=headers.get("From", "unknown"),
        )


class GoogleCalendarProvider:
    BASE_URL = "https://www.googleapis.com/calendar/v3/calendars/primary"

    def __init__(self, *, client: GoogleApiClient) -> None:
        self._client = client

    def list_events(self, day: str) -> list[CalendarEvent]:
        time_min = f"{day}T00:00:00Z"
        time_max = f"{day}T23:59:59Z"
        payload = self._client.request_json(
            method="GET",
            url=(
                f"{self.BASE_URL}/events?singleEvents=true&orderBy=startTime"
                f"&timeMin={time_min}&timeMax={time_max}"
            ),
        )
        return [self._to_calendar_event(item) for item in payload.get("items", [])]

    def create_event(self, title: str, starts_at: str, ends_at: str) -> CalendarEvent:
        payload = self._client.request_json(
            method="POST",
            url=f"{self.BASE_URL}/events",
            body={
                "summary": title,
                "start": {"dateTime": starts_at},
                "end": {"dateTime": ends_at},
            },
        )
        return self._to_calendar_event(payload)

    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        starts_at: str | None = None,
        ends_at: str | None = None,
    ) -> CalendarEvent:
        body: dict[str, object] = {}
        if title is not None:
            body["summary"] = title
        if starts_at is not None:
            body["start"] = {"dateTime": starts_at}
        if ends_at is not None:
            body["end"] = {"dateTime": ends_at}
        payload = self._client.request_json(
            method="PATCH",
            url=f"{self.BASE_URL}/events/{event_id}",
            body=body,
        )
        return self._to_calendar_event(payload)

    def delete_event(self, event_id: str) -> None:
        self._client.request_json(
            method="DELETE",
            url=f"{self.BASE_URL}/events/{event_id}",
        )

    def _to_calendar_event(self, payload: dict) -> CalendarEvent:
        return CalendarEvent(
            event_id=payload["id"],
            title=payload.get("summary", "(untitled event)"),
            starts_at=payload.get("start", {}).get("dateTime", payload.get("start", {}).get("date", "")),
            ends_at=payload.get("end", {}).get("dateTime", payload.get("end", {}).get("date", "")),
        )


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


def _gmail_headers(message_payload: dict) -> dict[str, str]:
    headers = message_payload.get("payload", {}).get("headers", [])
    return {item["name"]: item["value"] for item in headers if "name" in item and "value" in item}
