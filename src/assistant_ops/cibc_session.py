from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from assistant_ops.cibc_parser import CibcSnapshotParser, StatementAccountRef, StatementDownloadRef
from assistant_ops.cibc_login_parser import CibcLoginSnapshotParser
from assistant_ops.credentials import SecretReader
from assistant_ops.playwright_runner import PlaywrightCli


class CibcSessionManager:
    LOGIN_URL = "https://www.cibc.com/en/personal-banking.html"
    MY_DOCUMENTS_URL = (
        "https://www.cibconline.cibc.com/ebm-resources/public/my-documents/client/index.html"
        "#/summary?locale=en&channel=web"
    )
    ACCOUNT_STATEMENTS_URL = (
        "https://www.cibconline.cibc.com/ebm-resources/public/my-documents/client/index.html"
        "#/account-statements?locale=en&channel=web"
    )
    POST_SUBMIT_ATTEMPTS = 5
    POST_SUBMIT_DELAY_SECONDS = 1.0
    SNAPSHOT_ATTEMPTS = 5
    SNAPSHOT_DELAY_SECONDS = 1.0

    def __init__(self, *, playwright: PlaywrightCli, workspace_root: Path) -> None:
        self._playwright = playwright
        self._workspace_root = workspace_root
        self._login_parser = CibcLoginSnapshotParser()
        self._account_parser = CibcSnapshotParser()

    def open_login(self) -> dict[str, str]:
        output = self._playwright.open(self.LOGIN_URL, headed=True)
        return {
            "institution": "CIBC",
            "url": self.LOGIN_URL,
            "status": "browser-opened",
            "message": "Complete sign-in manually in the opened browser, then run capture.",
            "output": output,
        }

    def open_my_documents(self) -> dict[str, str]:
        output = self._playwright.open(self.MY_DOCUMENTS_URL, headed=True)
        return {
            "institution": "CIBC",
            "url": self.MY_DOCUMENTS_URL,
            "status": "browser-opened",
            "message": "My Documents opened. If prompted, complete sign-in manually, then capture a snapshot.",
            "output": output,
        }

    def open_account_statements(self) -> dict[str, str]:
        output = self._playwright.open(self.ACCOUNT_STATEMENTS_URL, headed=True)
        return {
            "institution": "CIBC",
            "url": self.ACCOUNT_STATEMENTS_URL,
            "status": "browser-opened",
            "message": "Account statements opened. If prompted, complete sign-in manually, then capture a snapshot.",
            "output": output,
        }

    def auto_sign_in(
        self,
        *,
        credential_provider: SecretReader,
        card_number_service: str,
        card_number_account: str,
        password_service: str,
        password_account: str,
    ) -> dict[str, str]:
        if not credential_provider.is_available():
            raise RuntimeError("macOS Keychain CLI is not available.")

        self._playwright.open(self.LOGIN_URL, headed=True)
        public_snapshot = self.capture_authenticated_snapshot()
        public_snapshot_path = self.resolve_snapshot_path(public_snapshot["snapshot_path"])
        existing_accounts = self._account_parser.parse_accounts(public_snapshot_path)
        if existing_accounts:
            return {
                "institution": "CIBC",
                "status": "authenticated",
                "snapshot_path": public_snapshot["snapshot_path"],
                "accounts_detected": str(len(existing_accounts)),
                "message": "Existing authenticated CIBC session detected.",
                "output": public_snapshot["output"],
            }
        sign_on_ref = self._login_parser.parse_public_login(public_snapshot_path)
        self._playwright.click(sign_on_ref)

        card_snapshot = self.capture_authenticated_snapshot()
        card_snapshot_path = self.resolve_snapshot_path(card_snapshot["snapshot_path"])
        card_step = self._login_parser.parse_card_step(card_snapshot_path)
        if card_step.cookie_close_ref:
            self._playwright.click(card_step.cookie_close_ref)
        self._playwright.fill(
            card_step.card_number_ref,
            credential_provider.read(service=card_number_service, account=card_number_account),
        )
        self._playwright.click(card_step.continue_ref)

        password_snapshot = self.capture_authenticated_snapshot()
        password_snapshot_path = self.resolve_snapshot_path(password_snapshot["snapshot_path"])
        password_step = self._login_parser.parse_password_step(password_snapshot_path)
        if password_step.cookie_close_ref:
            self._playwright.click(password_step.cookie_close_ref)
        self._playwright.fill(
            password_step.password_ref,
            credential_provider.read(service=password_service, account=password_account),
        )
        self._playwright.click(password_step.submit_ref)

        last_snapshot: dict[str, str] | None = None
        for attempt in range(self.POST_SUBMIT_ATTEMPTS):
            if attempt > 0:
                time.sleep(self.POST_SUBMIT_DELAY_SECONDS)
            last_snapshot = self.capture_authenticated_snapshot()
            snapshot_path = self.resolve_snapshot_path(last_snapshot["snapshot_path"])
            accounts = self._account_parser.parse_accounts(snapshot_path)
            if accounts:
                return {
                    "institution": "CIBC",
                    "status": "authenticated",
                    "snapshot_path": last_snapshot["snapshot_path"],
                    "accounts_detected": str(len(accounts)),
                    "message": "Credentials submitted and authenticated session detected.",
                    "output": last_snapshot["output"],
                }
            if self._login_parser.indicates_mfa_challenge(snapshot_path):
                return {
                    "institution": "CIBC",
                    "status": "mfa-required",
                    "snapshot_path": last_snapshot["snapshot_path"],
                    "message": "Credentials submitted. Complete MFA in the browser, then continue with snapshot capture.",
                    "output": last_snapshot["output"],
                }

        if last_snapshot is None:
            raise RuntimeError("CIBC sign-in did not produce a post-submit snapshot.")
        return {
            "institution": "CIBC",
            "status": "follow-up-required",
            "snapshot_path": last_snapshot["snapshot_path"],
            "message": "Credentials submitted, but the session did not reach an authenticated account page automatically.",
            "output": last_snapshot["output"],
        }

    def capture_authenticated_snapshot(self) -> dict[str, str]:
        snapshot = self._playwright.snapshot()
        return {
            "institution": "CIBC",
            "status": "snapshot-captured",
            "snapshot_path": snapshot["snapshot_path"],
            "message": (
                "Snapshot captured. Use this artifact to map post-login selectors for account and "
                "statement extraction."
            ),
            "output": snapshot["output"],
        }

    def download_statement(
        self,
        *,
        credential_provider: SecretReader,
        card_number_service: str,
        card_number_account: str,
        password_service: str,
        password_account: str,
        account_id: str,
        month: str,
        target_path: Path,
    ) -> dict[str, str]:
        sign_in = self.auto_sign_in(
            credential_provider=credential_provider,
            card_number_service=card_number_service,
            card_number_account=card_number_account,
            password_service=password_service,
            password_account=password_account,
        )
        if sign_in["status"] != "authenticated":
            raise RuntimeError(f"CIBC sign-in did not complete automatically: {sign_in['status']}")

        self._playwright.goto(self.ACCOUNT_STATEMENTS_URL)
        account_choice = self._wait_for_statement_account(account_id=account_id)
        self._playwright.click(account_choice.ref)

        statement_choice = self._wait_for_statement_download(month=month)
        download_output = self._playwright.click(statement_choice.ref)
        downloaded_path = self._extract_download_path(download_output)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(downloaded_path), str(target_path))

        return {
            "institution": "CIBC",
            "account_id": account_id,
            "month": month,
            "statement_label": statement_choice.label,
            "statement_route": statement_choice.route or "#",
            "downloaded_from": str(downloaded_path),
            "target_path": str(target_path),
            "status": "downloaded-live-session",
        }

    def latest_snapshot_path(self) -> Path:
        snapshots = sorted((self._workspace_root / ".playwright-cli").glob("page-*.yml"), reverse=True)
        if not snapshots:
            raise FileNotFoundError("No Playwright snapshot files found.")
        return snapshots[0]

    def resolve_snapshot_path(self, snapshot_ref: str) -> Path:
        relative = snapshot_ref.removeprefix("./")
        return self._workspace_root / relative

    def _match_statement_account(self, *, account_id: str, refs: list[StatementAccountRef]) -> StatementAccountRef:
        account_slug = account_id.split("_")[2]
        for ref in refs:
            visible_digits = re.sub(r"[^0-9]", "", ref.visible_number)
            type_slug = re.sub(r"[^a-z0-9]+", "-", ref.account_type.lower()).strip("-")
            suffix_matches = (
                (len(visible_digits) >= 6 and account_id.endswith(visible_digits[-6:]))
                or (len(visible_digits) >= 4 and account_id.endswith(visible_digits[-4:]))
            )
            type_matches = account_slug == type_slug or account_slug in type_slug or type_slug in account_slug
            if suffix_matches and type_matches:
                return ref
        raise ValueError(f"No statement account selector found for {account_id}")

    def _match_statement_download(self, *, month: str, refs: list[StatementDownloadRef]) -> StatementDownloadRef:
        for ref in refs:
            if ref.month == month:
                return ref
        raise ValueError(f"No statement selector found for month {month}")

    def _extract_download_path(self, output: str) -> Path:
        match = re.search(r'Downloaded file .* to "(?P<path>[^"]+)"', output)
        if not match:
            raise ValueError("Could not determine downloaded file path from Playwright output.")
        return self._workspace_root / match.group("path").removeprefix("./")

    def _wait_for_statement_account(self, *, account_id: str) -> StatementAccountRef:
        last_error: Exception | None = None
        for attempt in range(self.SNAPSHOT_ATTEMPTS):
            if attempt > 0:
                time.sleep(self.SNAPSHOT_DELAY_SECONDS)
            snapshot_path = self._capture_snapshot_path_with_content()
            refs = self._account_parser.parse_statement_account_refs(snapshot_path)
            if not refs:
                continue
            try:
                return self._match_statement_account(account_id=account_id, refs=refs)
            except ValueError as exc:
                last_error = exc
        raise last_error or ValueError(f"No statement account selector found for {account_id}")

    def _wait_for_statement_download(self, *, month: str) -> StatementDownloadRef:
        last_error: Exception | None = None
        for attempt in range(self.SNAPSHOT_ATTEMPTS):
            if attempt > 0:
                time.sleep(self.SNAPSHOT_DELAY_SECONDS)
            snapshot_path = self._capture_snapshot_path_with_content()
            refs = self._account_parser.parse_statement_download_refs(snapshot_path)
            if not refs:
                continue
            try:
                return self._match_statement_download(month=month, refs=refs)
            except ValueError as exc:
                last_error = exc
        raise last_error or ValueError(f"No statement selector found for month {month}")

    def _capture_snapshot_path_with_content(self) -> Path:
        last_path: Path | None = None
        for attempt in range(self.SNAPSHOT_ATTEMPTS):
            if attempt > 0:
                time.sleep(self.SNAPSHOT_DELAY_SECONDS)
            snapshot = self.capture_authenticated_snapshot()
            last_path = self.resolve_snapshot_path(snapshot["snapshot_path"])
            if last_path.exists() and last_path.stat().st_size > 0:
                return last_path
        if last_path is None:
            raise FileNotFoundError("No Playwright snapshot file was produced.")
        raise ValueError(f"Snapshot remained empty after retries: {last_path}")
