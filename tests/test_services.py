from pathlib import Path

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
from assistant_ops.policy import PolicyEngine
from assistant_ops.playwright_runner import PlaywrightCli
from assistant_ops.services import GuardedService


def build_service(tmp_path: Path) -> GuardedService:
    class FakeRunner:
        snapshot_name = ".playwright-cli/page-2026-03-09T13-51-37-713Z.yml"

        def run(self, args: list[str], cwd: Path) -> str:
            if "snapshot" in args:
                return f"### Snapshot\n- [Snapshot]({self.snapshot_name})"
            return "browser opened"

    (tmp_path / ".playwright-cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".playwright-cli" / "page-2026-03-09T13-51-37-713Z.yml").write_text(
        "\n".join(
            [
                '- heading "Deposit Accounts" [level=2] [ref=e1]',
                '- heading "Chequing" [level=3] [ref=e2]',
                '- generic [ref=e3]: 01141-82-65631',
                '- paragraph [ref=e4]: $4,819.04',
                '- heading "Lending Accounts" [level=2] [ref=e5]',
                '- heading "Line of Credit" [level=3] [ref=e6]',
                '- generic [ref=e7]: 00902-32-31437',
                '- paragraph [ref=e8]: $0.00',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "page-2026-03-09T13-50-01-422Z.yml").write_text(
        "\n".join(
            [
                '- link "February 1 to 28, 2026" [ref=e218] [cursor=pointer]:',
                '  - /url: "#/statements/doc-1"',
                '  - generic [ref=e223]: February 1 to 28, 2026',
                '- link "January 1 to 31, 2026" [ref=e225] [cursor=pointer]:',
                '  - /url: "#/statements/doc-2"',
                '  - generic [ref=e230]: January 1 to 31, 2026',
            ]
        ),
        encoding="utf-8",
    )

    runner = FakeRunner()
    session_manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    return GuardedService(
        policy_engine=PolicyEngine(),
        approval_store=ApprovalStore(tmp_path / "approvals.json"),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
        workspace_root=tmp_path,
        email_provider=JsonEmailProvider(tmp_path / "email.json"),
        calendar_provider=JsonCalendarProvider(tmp_path / "calendar.json"),
        accounting_provider=FileAccountingProvider(),
        cibc_session_manager=session_manager,
        banking_provider=LiveCibcBankingProvider(
            session_manager=session_manager,
            parser=CibcSnapshotParser(),
        ),
    )


def test_write_is_blocked_without_approval(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.run(
        tool_name="send_email",
        target="draft_123",
        details={"draft_id": "draft_123"},
    )

    assert result.ok is False
    assert "requires an approval token" in result.message


def test_write_succeeds_with_matching_approval(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    draft = service.draft_email_reply("thr_demo_001", "Approved to send.")
    approval = service.create_approval_request(
        action="send_email",
        target=draft.data["draft_id"],
        reason="User confirmed send.",
    )

    result = service.send_email(draft.data["draft_id"], approval_id=approval.data["approval_id"])

    assert result.ok is True
    assert result.data["draft_id"] == draft.data["draft_id"]
    assert result.data["sent"] is True


def test_download_target_path_stays_under_workspace(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    path = service.download_target_path(account_id="td_chequing", month="2026-03")

    assert path == tmp_path / "data" / "downloads" / "td_chequing_2026-03.pdf"


def test_calendar_create_persists_event_with_approval(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    approval = service.create_approval_request(
        action="create_calendar_event",
        target="Budget review",
        reason="User confirmed creation.",
    )

    result = service.create_calendar_event(
        title="Budget review",
        starts_at="2026-03-10T10:00:00-05:00",
        ends_at="2026-03-10T10:30:00-05:00",
        approval_id=approval.data["approval_id"],
    )

    assert result.ok is True
    assert result.data["title"] == "Budget review"


def test_calendar_update_and_delete_require_approval_and_mutate_state(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    create_approval = service.create_approval_request(
        action="create_calendar_event",
        target="Budget review",
        reason="Create baseline event.",
    )
    created = service.create_calendar_event(
        title="Budget review",
        starts_at="2026-03-10T10:00:00-05:00",
        ends_at="2026-03-10T10:30:00-05:00",
        approval_id=create_approval.data["approval_id"],
    )
    update_approval = service.create_approval_request(
        action="update_calendar_event",
        target=created.data["event_id"],
        reason="Adjust event title.",
    )
    updated = service.update_calendar_event(
        event_id=created.data["event_id"],
        title="Updated budget review",
        approval_id=update_approval.data["approval_id"],
    )
    delete_approval = service.create_approval_request(
        action="delete_calendar_event",
        target=created.data["event_id"],
        reason="Remove test event.",
    )
    deleted = service.delete_calendar_event(
        created.data["event_id"],
        approval_id=delete_approval.data["approval_id"],
    )

    assert updated.ok is True
    assert updated.data["title"] == "Updated budget review"
    assert deleted.ok is True
    assert deleted.data["deleted"] is True


def test_email_threads_are_loaded_from_json_provider(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.list_email_threads(limit=1)

    assert result.ok is True
    assert len(result.data["threads"]) == 1


def test_email_search_and_thread_detail_use_provider(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    search = service.search_email_threads("quarterly", limit=5)
    detail = service.get_email_thread("thr_demo_001")

    assert search.ok is True
    assert len(search.data["threads"]) == 1
    assert detail.ok is True
    assert detail.data["thread_id"] == "thr_demo_001"


def test_cibc_accounts_are_loaded_from_live_snapshot(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.list_cibc_accounts()

    assert result.ok is True
    assert result.data["institution"] == "CIBC"
    assert len(result.data["accounts"]) == 2


def test_cibc_balance_lookup_returns_account_snapshot(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.get_cibc_account_balance("cibc_deposit_chequing_265631")

    assert result.ok is True
    assert result.data["account_type"] == "Chequing"
    assert result.data["balance"] == "4819.04"


def test_cibc_statement_download_is_planned_under_workspace(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service._cibc_session._playwright._runner.snapshot_name = ".playwright-cli/page-2026-03-09T13-50-01-422Z.yml"  # noqa: SLF001

    result = service.download_cibc_statement("cibc_deposit_chequing_265631", "2026-02")

    assert result.ok is True
    assert result.data["institution"] == "CIBC"
    assert result.data["statement_label"] == "February 1 to 28, 2026"
    assert result.data["statement_route"] == "#/statements/doc-1"
    assert result.data["target_path"] == str(
        tmp_path / "data" / "downloads" / "cibc_deposit_chequing_265631_2026-02.pdf"
    )


def test_cibc_statement_download_uses_live_session_when_credentials_configured(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    class FakeSecretReader:
        def is_available(self) -> bool:
            return True

        def read(self, *, service: str, account: str) -> str:
            return "secret"

    def fake_download_statement(**kwargs: object) -> dict[str, str]:
        return {
            "institution": "CIBC",
            "account_id": str(kwargs["account_id"]),
            "month": str(kwargs["month"]),
            "statement_label": "February 1 to 28, 2026",
            "statement_route": "#/statements/doc-1",
            "downloaded_from": str(tmp_path / ".playwright-cli" / "onlineStatement-2026-02-28.pdf"),
            "target_path": str(kwargs["target_path"]),
            "status": "downloaded-live-session",
        }

    service._credentials = FakeSecretReader()  # noqa: SLF001
    service._cibc_card_number_service = "assistant-ops.cibc"  # noqa: SLF001
    service._cibc_card_number_account = "card-number"  # noqa: SLF001
    service._cibc_password_service = "assistant-ops.cibc"  # noqa: SLF001
    service._cibc_password_account = "password"  # noqa: SLF001
    service._cibc_session.download_statement = fake_download_statement  # type: ignore[method-assign] # noqa: SLF001

    result = service.download_cibc_statement("cibc_deposit_chequing_265631", "2026-02")

    assert result.ok is True
    assert result.data["status"] == "downloaded-live-session"


def test_open_cibc_login_records_browser_open(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.open_cibc_login()

    assert result.ok is True
    assert result.data["institution"] == "CIBC"
    assert result.data["status"] == "browser-opened"


def test_capture_cibc_session_snapshot_returns_snapshot_path(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.capture_cibc_session_snapshot()

    assert result.ok is True
    assert result.data["snapshot_path"] == ".playwright-cli/page-2026-03-09T13-51-37-713Z.yml"


def test_open_cibc_account_statements_returns_route_metadata(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.open_cibc_account_statements()

    assert result.ok is True
    assert "#/account-statements" in result.data["url"]


def test_list_cibc_statements_returns_live_entries(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    service._cibc_session._playwright._runner.snapshot_name = ".playwright-cli/page-2026-03-09T13-50-01-422Z.yml"  # noqa: SLF001

    result = service.list_cibc_statements("cibc_deposit_chequing_265631")

    assert result.ok is True
    assert len(result.data["statements"]) == 2
    assert result.data["statements"][0]["month"] == "2026-02"
