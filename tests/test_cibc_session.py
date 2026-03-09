from pathlib import Path

from assistant_ops.cibc_login_parser import CibcLoginSnapshotParser
from assistant_ops.cibc_session import CibcSessionManager
from assistant_ops.playwright_runner import PlaywrightCli


class FakeRunner:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[list[str]] = []

    def run(self, args: list[str], cwd: Path) -> str:
        self.calls.append(args)
        return self.output


class FakeSecretReader:
    def is_available(self) -> bool:
        return True

    def read(self, *, service: str, account: str) -> str:
        mapping = {
            ("assistant-ops.cibc", "card-number"): "4500123412341234",
            ("assistant-ops.cibc", "password"): "secret",
        }
        return mapping[(service, account)]


def test_playwright_open_uses_headed_flag(tmp_path: Path) -> None:
    runner = FakeRunner("browser opened")
    cli = PlaywrightCli(
        pwcli_path=Path("/tmp/playwright_cli.sh"),
        workspace_root=tmp_path,
        session_name="cibc-banking",
        runner=runner,
    )

    output = cli.open("https://www.cibc.com/en/personal-banking.html")

    assert output == "browser opened"
    assert runner.calls[0] == [
        "/tmp/playwright_cli.sh",
        "--session",
        "cibc-banking",
        "open",
        "https://www.cibc.com/en/personal-banking.html",
        "--headed",
    ]


def test_snapshot_extracts_snapshot_path(tmp_path: Path) -> None:
    runner = FakeRunner("### Snapshot\n- [Snapshot](.playwright-cli/page-123.yml)")
    cli = PlaywrightCli(
        pwcli_path=Path("/tmp/playwright_cli.sh"),
        workspace_root=tmp_path,
        session_name="cibc-banking",
        runner=runner,
    )

    snapshot = cli.snapshot()

    assert snapshot["snapshot_path"] == ".playwright-cli/page-123.yml"


def test_cibc_session_manager_returns_login_metadata(tmp_path: Path) -> None:
    runner = FakeRunner("browser opened")
    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    result = manager.open_login()

    assert result["institution"] == "CIBC"
    assert result["status"] == "browser-opened"


def test_cibc_session_manager_exposes_account_statements_route(tmp_path: Path) -> None:
    runner = FakeRunner("browser opened")
    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    result = manager.open_account_statements()

    assert result["institution"] == "CIBC"
    assert "#/account-statements" in result["url"]


def test_login_parser_extracts_card_step_refs(tmp_path: Path) -> None:
    snapshot = tmp_path / "page.yml"
    snapshot.write_text(
        '\n'.join(
            [
                '- textbox "Card number" [ref=e45]',
                '- button "Continue" [ref=e66] [cursor=pointer]',
                '- button "Close" [ref=e101] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )

    refs = CibcLoginSnapshotParser().parse_card_step(snapshot)

    assert refs.card_number_ref == "e45"
    assert refs.continue_ref == "e66"
    assert refs.cookie_close_ref == "e101"


def test_login_parser_detects_mfa_keywords(tmp_path: Path) -> None:
    snapshot = tmp_path / "page.yml"
    snapshot.write_text(
        '- generic [ref=e1]: Enter verification code to continue',
        encoding="utf-8",
    )

    assert CibcLoginSnapshotParser().indicates_mfa_challenge(snapshot) is True


def test_cibc_auto_sign_in_submits_to_mfa(tmp_path: Path) -> None:
    class SequencedRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []
            self.snapshot_calls = 0

        def run(self, args: list[str], cwd: Path) -> str:
            self.calls.append(args)
            if "snapshot" in args:
                self.snapshot_calls += 1
                mapping = {
                    1: ".playwright-cli/public.yml",
                    2: ".playwright-cli/card.yml",
                    3: ".playwright-cli/password.yml",
                    4: ".playwright-cli/mfa.yml",
                }
                return f"### Snapshot\n- [Snapshot]({mapping[self.snapshot_calls]})"
            if "open" in args:
                return "browser opened"
            return ""

    (tmp_path / ".playwright-cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".playwright-cli" / "public.yml").write_text(
        '- button "Sign on to CIBC Online Banking." [ref=e61] [cursor=pointer]',
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "card.yml").write_text(
        '\n'.join(
            [
                '- textbox "Card number" [ref=e45]',
                '- button "Continue" [ref=e66] [cursor=pointer]',
                '- button "Close" [ref=e101] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "password.yml").write_text(
        '\n'.join(
            [
                '- textbox "Password" [ref=e145]',
                '- button "Sign on" [ref=e166] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "mfa.yml").write_text(
        '- generic [ref=e1]: Enter verification code to continue',
        encoding="utf-8",
    )
    runner = SequencedRunner()
    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    result = manager.auto_sign_in(
        credential_provider=FakeSecretReader(),
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
    )

    assert result["status"] == "mfa-required"
    assert result["snapshot_path"] == ".playwright-cli/mfa.yml"


def test_cibc_auto_sign_in_continues_without_mfa(tmp_path: Path) -> None:
    class SequencedRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []
            self.snapshot_calls = 0

        def run(self, args: list[str], cwd: Path) -> str:
            self.calls.append(args)
            if "snapshot" in args:
                self.snapshot_calls += 1
                mapping = {
                    1: ".playwright-cli/public.yml",
                    2: ".playwright-cli/card.yml",
                    3: ".playwright-cli/password.yml",
                    4: ".playwright-cli/post-submit.yml",
                    5: ".playwright-cli/authenticated.yml",
                }
                return f"### Snapshot\n- [Snapshot]({mapping[self.snapshot_calls]})"
            if "open" in args:
                return "browser opened"
            return ""

    (tmp_path / ".playwright-cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".playwright-cli" / "public.yml").write_text(
        '- button "Sign on to CIBC Online Banking." [ref=e61] [cursor=pointer]',
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "card.yml").write_text(
        '\n'.join(
            [
                '- textbox "Card number" [ref=e45]',
                '- button "Continue" [ref=e66] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "password.yml").write_text(
        '\n'.join(
            [
                '- textbox "Password" [ref=e145]',
                '- button "Sign on" [ref=e166] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "post-submit.yml").write_text(
        '- img "Signon." [ref=e1]',
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "authenticated.yml").write_text(
        '\n'.join(
            [
                '- heading "Deposit Accounts" [level=2]',
                '- heading "Chequing" [level=3]',
                '- generic [ref=e4]: 265631',
                '- paragraph [ref=e5]: 4,819.04',
            ]
        ),
        encoding="utf-8",
    )
    runner = SequencedRunner()
    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    result = manager.auto_sign_in(
        credential_provider=FakeSecretReader(),
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
    )

    assert result["status"] == "authenticated"
    assert result["snapshot_path"] == ".playwright-cli/authenticated.yml"
    assert result["accounts_detected"] == "1"


def test_cibc_auto_sign_in_reuses_existing_authenticated_session(tmp_path: Path) -> None:
    class SequencedRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def run(self, args: list[str], cwd: Path) -> str:
            self.calls.append(args)
            if "snapshot" in args:
                return "### Snapshot\n- [Snapshot](.playwright-cli/authenticated.yml)"
            return "ok"

    (tmp_path / ".playwright-cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".playwright-cli" / "authenticated.yml").write_text(
        '\n'.join(
            [
                '- heading "Deposit Accounts" [level=2]',
                '- heading "Chequing" [level=3]',
                '- generic [ref=e4]: 265631',
                '- paragraph [ref=e5]: 4,819.04',
            ]
        ),
        encoding="utf-8",
    )

    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=SequencedRunner(),
        ),
        workspace_root=tmp_path,
    )

    result = manager.auto_sign_in(
        credential_provider=FakeSecretReader(),
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
    )

    assert result["status"] == "authenticated"
    assert result["accounts_detected"] == "1"


def test_cibc_download_statement_moves_downloaded_file(tmp_path: Path) -> None:
    class SequencedRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []
            self.snapshot_calls = 0

        def run(self, args: list[str], cwd: Path) -> str:
            self.calls.append(args)
            if "snapshot" in args:
                self.snapshot_calls += 1
                mapping = {
                    1: ".playwright-cli/public.yml",
                    2: ".playwright-cli/card.yml",
                    3: ".playwright-cli/password.yml",
                    4: ".playwright-cli/authenticated.yml",
                    5: ".playwright-cli/account-statements.yml",
                    6: ".playwright-cli/document-list.yml",
                }
                return f"### Snapshot\n- [Snapshot]({mapping[self.snapshot_calls]})"
            if "click" in args and "e132" in args:
                return (
                    "### Events\n"
                    '- Downloading file onlineStatement_2026-02-28.pdf ...\n'
                    '- Downloaded file onlineStatement_2026-02-28.pdf to ".playwright-cli/onlineStatement-2026-02-28.pdf"\n'
                )
            if "open" in args or "goto" in args or "fill" in args or "click" in args:
                return "ok"
            return ""

    (tmp_path / ".playwright-cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".playwright-cli" / "public.yml").write_text(
        '- button "Sign on to CIBC Online Banking." [ref=e61] [cursor=pointer]',
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "card.yml").write_text(
        '\n'.join(
            [
                '- textbox "Card number" [ref=e45]',
                '- button "Continue" [ref=e66] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "password.yml").write_text(
        '\n'.join(
            [
                '- textbox "Password" [ref=e145]',
                '- button "Sign on" [ref=e166] [cursor=pointer]',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "authenticated.yml").write_text(
        '\n'.join(
            [
                '- heading "Deposit Accounts" [level=2]',
                '- heading "Chequing" [level=3]',
                '- generic [ref=e4]: 265631',
                '- paragraph [ref=e5]: 4,819.04',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "account-statements.yml").write_text(
        '\n'.join(
            [
                '- link "Chequing . 8265631" [ref=e26] [cursor=pointer]:',
                '  - /url: "#/statements/doc-1"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".playwright-cli" / "document-list.yml").write_text(
        '\n'.join(
            [
                '- link "February 1 to 28, 2026" [ref=e132] [cursor=pointer]:',
                '  - /url: "#/statements/doc-1"',
            ]
        ),
        encoding="utf-8",
    )
    download_path = tmp_path / ".playwright-cli" / "onlineStatement-2026-02-28.pdf"
    download_path.write_text("pdf-bytes", encoding="utf-8")
    runner = SequencedRunner()
    manager = CibcSessionManager(
        playwright=PlaywrightCli(
            pwcli_path=Path("/tmp/playwright_cli.sh"),
            workspace_root=tmp_path,
            session_name="cibc-banking",
            runner=runner,
        ),
        workspace_root=tmp_path,
    )

    target_path = tmp_path / "downloads" / "statement.pdf"
    result = manager.download_statement(
        credential_provider=FakeSecretReader(),
        card_number_service="assistant-ops.cibc",
        card_number_account="card-number",
        password_service="assistant-ops.cibc",
        password_account="password",
        account_id="cibc_deposit_chequing_265631",
        month="2026-02",
        target_path=target_path,
    )

    assert result["status"] == "downloaded-live-session"
    assert result["statement_label"] == "February 1 to 28, 2026"
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == "pdf-bytes"
