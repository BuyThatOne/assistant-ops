from __future__ import annotations

from pathlib import Path

from assistant_ops.adapters import AccountingProvider, BankingProvider, CalendarProvider, EmailProvider
from assistant_ops.approvals import ApprovalStore
from assistant_ops.audit import AuditLogger
from assistant_ops.cibc_session import CibcSessionManager
from assistant_ops.credentials import SecretReader
from assistant_ops.models import AuditRecord, ToolResult
from assistant_ops.policy import PolicyDecision, PolicyEngine


class GuardedService:
    def __init__(
        self,
        *,
        policy_engine: PolicyEngine,
        approval_store: ApprovalStore,
        audit_logger: AuditLogger,
        workspace_root: Path,
        email_provider: EmailProvider,
        calendar_provider: CalendarProvider,
        accounting_provider: AccountingProvider,
        banking_provider: BankingProvider,
        cibc_session_manager: CibcSessionManager | None = None,
        credential_provider: SecretReader | None = None,
        cibc_card_number_service: str | None = None,
        cibc_card_number_account: str | None = None,
        cibc_password_service: str | None = None,
        cibc_password_account: str | None = None,
        actor: str = "local-operator",
    ) -> None:
        self._policy = policy_engine
        self._approvals = approval_store
        self._audit = audit_logger
        self._workspace_root = workspace_root
        self._email = email_provider
        self._calendar = calendar_provider
        self._accounting = accounting_provider
        self._banking = banking_provider
        self._cibc_session = cibc_session_manager
        self._credentials = credential_provider
        self._cibc_card_number_service = cibc_card_number_service
        self._cibc_card_number_account = cibc_card_number_account
        self._cibc_password_service = cibc_password_service
        self._cibc_password_account = cibc_password_account
        self._actor = actor

    def create_approval_request(self, *, action: str, target: str, reason: str | None) -> ToolResult:
        approval = self._approvals.create(action=action, target=target, reason=reason)
        self._audit.record(
            AuditRecord(
                actor=self._actor,
                tool_name="create_approval_request",
                action_target=target,
                risk=self._policy.evaluate(action).risk,
                approval_required=False,
                approval_id=approval.approval_id,
                status="issued",
                details={"action": action},
            )
        )
        return ToolResult(
            ok=True,
            message="Approval request created.",
            data=approval.model_dump(mode="json"),
        )

    def run(
        self,
        *,
        tool_name: str,
        target: str,
        details: dict[str, object],
        approval_id: str | None = None,
    ) -> ToolResult:
        decision = self._policy.evaluate(tool_name)
        if decision.approval_required:
            if approval_id is None:
                self._record_blocked(decision=decision, target=target, details=details)
                return ToolResult(
                    ok=False,
                    message=f"{tool_name} requires an approval token.",
                    data={"tool_name": tool_name, "target": target},
                )
            consumed = self._approvals.consume(approval_id, expected_action=tool_name)
            approval_id = consumed.approval_id

        self._audit.record(
            AuditRecord(
                actor=self._actor,
                tool_name=tool_name,
                action_target=target,
                risk=decision.risk,
                approval_required=decision.approval_required,
                approval_id=approval_id,
                status="ok",
                details=details,
            )
        )

        return ToolResult(ok=True, message=f"{tool_name} completed.", data=details)

    def list_recent_actions(self, limit: int = 20) -> ToolResult:
        records = [record.model_dump(mode="json") for record in self._audit.list_recent(limit)]
        return ToolResult(ok=True, message="Recent actions loaded.", data={"records": records})

    def list_email_threads(self, limit: int = 10) -> ToolResult:
        threads = [thread.model_dump(mode="json") for thread in self._email.list_threads(limit)]
        return self.run(
            tool_name="list_email_threads",
            target="primary-mailbox",
            details={"threads": threads},
        )

    def search_email_threads(self, query: str, limit: int = 10) -> ToolResult:
        threads = [thread.model_dump(mode="json") for thread in self._email.search_threads(query, limit)]
        return self.run(
            tool_name="search_email_threads",
            target=query,
            details={"query": query, "threads": threads},
        )

    def get_email_thread(self, thread_id: str) -> ToolResult:
        thread = self._email.get_thread(thread_id)
        return self.run(
            tool_name="get_email_thread",
            target=thread_id,
            details=thread,
        )

    def draft_email_reply(self, thread_id: str, body: str) -> ToolResult:
        draft = self._email.draft_reply(thread_id, body)
        return self.run(
            tool_name="draft_email_reply",
            target=thread_id,
            details=draft.model_dump(mode="json"),
        )

    def send_email(self, draft_id: str, approval_id: str | None = None) -> ToolResult:
        result = self.run(
            tool_name="send_email",
            target=draft_id,
            details={"draft_id": draft_id},
            approval_id=approval_id,
        )
        if not result.ok:
            return result
        sent = self._email.send_draft(draft_id)
        return ToolResult(ok=True, message="send_email completed.", data=sent.model_dump(mode="json"))

    def list_calendar_events(self, day: str) -> ToolResult:
        events = [event.model_dump(mode="json") for event in self._calendar.list_events(day)]
        return self.run(
            tool_name="list_calendar_events",
            target=day,
            details={"day": day, "events": events},
        )

    def create_calendar_event(
        self,
        *,
        title: str,
        starts_at: str,
        ends_at: str,
        approval_id: str | None = None,
    ) -> ToolResult:
        result = self.run(
            tool_name="create_calendar_event",
            target=title,
            details={"title": title, "starts_at": starts_at, "ends_at": ends_at},
            approval_id=approval_id,
        )
        if not result.ok:
            return result
        event = self._calendar.create_event(title, starts_at, ends_at)
        return ToolResult(
            ok=True,
            message="create_calendar_event completed.",
            data=event.model_dump(mode="json"),
        )

    def update_calendar_event(
        self,
        *,
        event_id: str,
        title: str | None = None,
        starts_at: str | None = None,
        ends_at: str | None = None,
        approval_id: str | None = None,
    ) -> ToolResult:
        result = self.run(
            tool_name="update_calendar_event",
            target=event_id,
            details={
                "event_id": event_id,
                "title": title,
                "starts_at": starts_at,
                "ends_at": ends_at,
            },
            approval_id=approval_id,
        )
        if not result.ok:
            return result
        event = self._calendar.update_event(
            event_id,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        return ToolResult(
            ok=True,
            message="update_calendar_event completed.",
            data=event.model_dump(mode="json"),
        )

    def delete_calendar_event(self, event_id: str, approval_id: str | None = None) -> ToolResult:
        result = self.run(
            tool_name="delete_calendar_event",
            target=event_id,
            details={"event_id": event_id},
            approval_id=approval_id,
        )
        if not result.ok:
            return result
        self._calendar.delete_event(event_id)
        return ToolResult(
            ok=True,
            message="delete_calendar_event completed.",
            data={"event_id": event_id, "deleted": True},
        )

    def download_statement(self, account_id: str, month: str) -> ToolResult:
        target_path = self.download_target_path(account_id=account_id, month=month)
        details = self._accounting.plan_statement_download(account_id, month, target_path)
        return self.run(
            tool_name="download_statement",
            target=account_id,
            details=details,
        )

    def list_cibc_accounts(self) -> ToolResult:
        accounts = [account.model_dump(mode="json") for account in self._banking.list_accounts()]
        return self.run(
            tool_name="list_cibc_accounts",
            target="cibc",
            details={"institution": "CIBC", "accounts": accounts},
        )

    def get_cibc_account_balance(self, account_id: str) -> ToolResult:
        account = self._banking.get_account(account_id)
        return self.run(
            tool_name="get_cibc_account_balance",
            target=account_id,
            details={
                "institution": account.institution,
                "account_id": account.account_id,
                "account_type": account.account_type,
                "currency": account.currency,
                "balance": account.balance,
                "available_balance": account.available_balance,
            },
        )

    def list_cibc_statements(self, account_id: str) -> ToolResult:
        statements = [entry.model_dump(mode="json") for entry in self._banking.list_statements(account_id)]
        return self.run(
            tool_name="list_cibc_statements",
            target=account_id,
            details={"institution": "CIBC", "account_id": account_id, "statements": statements},
        )

    def download_cibc_statement(self, account_id: str, month: str) -> ToolResult:
        target_path = self.download_target_path(account_id=account_id, month=month)
        if (
            self._cibc_session is not None
            and self._credentials is not None
            and self._cibc_card_number_service
            and self._cibc_card_number_account
            and self._cibc_password_service
            and self._cibc_password_account
        ):
            details = self._cibc_session.download_statement(
                credential_provider=self._credentials,
                card_number_service=self._cibc_card_number_service,
                card_number_account=self._cibc_card_number_account,
                password_service=self._cibc_password_service,
                password_account=self._cibc_password_account,
                account_id=account_id,
                month=month,
                target_path=target_path,
            )
        else:
            details = self._banking.plan_statement_download(account_id, month, target_path)
        return self.run(
            tool_name="download_cibc_statement",
            target=account_id,
            details=details,
        )

    def open_cibc_login(self) -> ToolResult:
        if self._cibc_session is None:
            raise RuntimeError("CIBC Playwright session manager is not configured.")
        details = self._cibc_session.open_login()
        return self.run(
            tool_name="open_cibc_login",
            target="cibc-login",
            details=details,
        )

    def open_cibc_my_documents(self) -> ToolResult:
        if self._cibc_session is None:
            raise RuntimeError("CIBC Playwright session manager is not configured.")
        details = self._cibc_session.open_my_documents()
        return self.run(
            tool_name="open_cibc_my_documents",
            target="cibc-my-documents",
            details=details,
        )

    def open_cibc_account_statements(self) -> ToolResult:
        if self._cibc_session is None:
            raise RuntimeError("CIBC Playwright session manager is not configured.")
        details = self._cibc_session.open_account_statements()
        return self.run(
            tool_name="open_cibc_account_statements",
            target="cibc-account-statements",
            details=details,
        )

    def capture_cibc_session_snapshot(self) -> ToolResult:
        if self._cibc_session is None:
            raise RuntimeError("CIBC Playwright session manager is not configured.")
        details = self._cibc_session.capture_authenticated_snapshot()
        return self.run(
            tool_name="capture_cibc_session_snapshot",
            target="cibc-session",
            details=details,
        )

    def capture_cibc_account_statements_snapshot(self) -> ToolResult:
        if self._cibc_session is None:
            raise RuntimeError("CIBC Playwright session manager is not configured.")
        details = self._cibc_session.capture_authenticated_snapshot()
        return self.run(
            tool_name="capture_cibc_account_statements_snapshot",
            target="cibc-account-statements",
            details=details,
        )

    def auto_sign_in_cibc(self) -> ToolResult:
        if self._cibc_session is None or self._credentials is None:
            raise RuntimeError("CIBC session manager or credential provider is not configured.")
        if (
            not self._cibc_card_number_service
            or not self._cibc_card_number_account
            or not self._cibc_password_service
            or not self._cibc_password_account
        ):
            raise RuntimeError("CIBC Keychain service/account settings are not configured.")
        details = self._cibc_session.auto_sign_in(
            credential_provider=self._credentials,
            card_number_service=self._cibc_card_number_service,
            card_number_account=self._cibc_card_number_account,
            password_service=self._cibc_password_service,
            password_account=self._cibc_password_account,
        )
        return self.run(
            tool_name="auto_sign_in_cibc",
            target="cibc-login",
            details=details,
        )

    def download_target_path(self, account_id: str, month: str) -> Path:
        return self._workspace_root / "data" / "downloads" / f"{account_id}_{month}.pdf"

    def _record_blocked(
        self,
        *,
        decision: PolicyDecision,
        target: str,
        details: dict[str, object],
    ) -> None:
        self._audit.record(
            AuditRecord(
                actor=self._actor,
                tool_name=decision.tool_name,
                action_target=target,
                risk=decision.risk,
                approval_required=True,
                status="blocked",
                details=details,
            )
        )
