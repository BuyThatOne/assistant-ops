from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from assistant_ops.adapters import (
    FileAccountingProvider,
    LiveCibcBankingProvider,
    JsonCalendarProvider,
    JsonEmailProvider,
)
from assistant_ops.cibc_parser import CibcSnapshotParser
from assistant_ops.approvals import ApprovalStore
from assistant_ops.audit import AuditLogger
from assistant_ops.cibc_session import CibcSessionManager
from assistant_ops.config import Settings
from assistant_ops.credentials import MacOSKeychainCredentialProvider
from assistant_ops.bootstrap import initialize_workspace
from assistant_ops.policy import PolicyEngine
from assistant_ops.playwright_runner import PlaywrightCli
from assistant_ops.services import GuardedService


def build_server(workspace_root: Path, *, actor: str = "local-operator") -> FastMCP:
    initialize_workspace(workspace_root)
    settings = Settings.for_workspace(workspace_root)
    audit_logger = AuditLogger(settings.audit_log_path)
    approvals = ApprovalStore(settings.approvals_path)
    cibc_session_manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=settings.pwcli_path,
            workspace_root=workspace_root,
            session_name=settings.cibc_playwright_session,
        ),
        workspace_root=workspace_root,
    )

    service = GuardedService(
        policy_engine=PolicyEngine(),
        approval_store=approvals,
        audit_logger=audit_logger,
        workspace_root=workspace_root,
        email_provider=JsonEmailProvider(settings.email_data_path),
        calendar_provider=JsonCalendarProvider(settings.calendar_data_path),
        accounting_provider=FileAccountingProvider(),
        banking_provider=LiveCibcBankingProvider(
            session_manager=cibc_session_manager,
            parser=CibcSnapshotParser(),
        ),
        cibc_session_manager=cibc_session_manager,
        credential_provider=MacOSKeychainCredentialProvider(security_path=settings.security_path),
        cibc_card_number_service=settings.cibc_card_number_service,
        cibc_card_number_account=settings.cibc_card_number_account,
        cibc_password_service=settings.cibc_password_service,
        cibc_password_account=settings.cibc_password_account,
        actor=actor,
    )

    mcp = FastMCP(
        name="assistant-ops",
        instructions=(
            "Production-oriented assistant server. Prefer read-only tools by default and "
            "require approval tokens for write actions."
        ),
    )

    @mcp.tool(description="Issue an approval request for a sensitive tool.")
    def create_approval_request(action: str, target: str, reason: str | None = None) -> dict:
        return service.create_approval_request(action=action, target=target, reason=reason).model_dump(
            mode="json"
        )

    @mcp.tool(description="List email threads from the primary mailbox.")
    def list_email_threads(limit: int = 10) -> dict:
        return service.list_email_threads(limit).model_dump(mode="json")

    @mcp.tool(description="Draft a reply for a given email thread without sending it.")
    def draft_email_reply(thread_id: str, body: str) -> dict:
        return service.draft_email_reply(thread_id, body).model_dump(mode="json")

    @mcp.tool(description="Send a previously prepared email draft. Requires approval.")
    def send_email(draft_id: str, approval_id: str | None = None) -> dict:
        return service.send_email(draft_id, approval_id=approval_id).model_dump(mode="json")

    @mcp.tool(description="List calendar events for a date.")
    def list_calendar_events(day: str) -> dict:
        return service.list_calendar_events(day).model_dump(mode="json")

    @mcp.tool(description="Create a calendar event. Requires approval.")
    def create_calendar_event(
        title: str,
        starts_at: str,
        ends_at: str,
        approval_id: str | None = None,
    ) -> dict:
        return service.create_calendar_event(
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            approval_id=approval_id,
        ).model_dump(mode="json")

    @mcp.tool(description="Plan a financial statement download and return the target file path.")
    def download_statement(account_id: str, month: str) -> dict:
        return service.download_statement(account_id, month).model_dump(mode="json")

    @mcp.tool(description="List configured CIBC accounts from the local banking adapter.")
    def list_cibc_accounts() -> dict:
        return service.list_cibc_accounts().model_dump(mode="json")

    @mcp.tool(description="Return the current balance snapshot for a configured CIBC account.")
    def get_cibc_account_balance(account_id: str) -> dict:
        return service.get_cibc_account_balance(account_id).model_dump(mode="json")

    @mcp.tool(description="List available statement entries for a CIBC account from the live statement list page.")
    def list_cibc_statements(account_id: str) -> dict:
        return service.list_cibc_statements(account_id).model_dump(mode="json")

    @mcp.tool(description="Plan a read-only CIBC statement download and return the target file path.")
    def download_cibc_statement(account_id: str, month: str) -> dict:
        return service.download_cibc_statement(account_id, month).model_dump(mode="json")

    @mcp.tool(description="Open the public CIBC login entrypoint in a headed browser for manual sign-in.")
    def open_cibc_login() -> dict:
        return service.open_cibc_login().model_dump(mode="json")

    @mcp.tool(description="Automatically fill CIBC credentials from macOS Keychain and submit the sign-in flow up to MFA.")
    def auto_sign_in_cibc() -> dict:
        return service.auto_sign_in_cibc().model_dump(mode="json")

    @mcp.tool(description="Open CIBC My Documents in a headed browser for supervised document access.")
    def open_cibc_my_documents() -> dict:
        return service.open_cibc_my_documents().model_dump(mode="json")

    @mcp.tool(description="Open the CIBC Account statements route in a headed browser.")
    def open_cibc_account_statements() -> dict:
        return service.open_cibc_account_statements().model_dump(mode="json")

    @mcp.tool(description="Capture a Playwright snapshot after manual CIBC sign-in.")
    def capture_cibc_session_snapshot() -> dict:
        return service.capture_cibc_session_snapshot().model_dump(mode="json")

    @mcp.tool(description="Capture a Playwright snapshot from the CIBC Account statements page.")
    def capture_cibc_account_statements_snapshot() -> dict:
        return service.capture_cibc_account_statements_snapshot().model_dump(mode="json")

    @mcp.tool(description="List recent audit log entries.")
    def list_recent_actions(limit: int = 20) -> dict:
        return service.list_recent_actions(limit=limit).model_dump(mode="json")

    return mcp
