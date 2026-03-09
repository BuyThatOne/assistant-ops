from pathlib import Path

from assistant_ops.cibc_parser import CibcSnapshotParser


def test_parser_extracts_cibc_accounts_from_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "page-2026-03-09T13-41-37-713Z.yml"
    snapshot.write_text(
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

    accounts = CibcSnapshotParser().parse_accounts(snapshot)

    assert len(accounts) == 2
    assert accounts[0].account_id == "cibc_deposit_chequing_265631"
    assert accounts[0].balance == "4819.04"
    assert accounts[1].account_id == "cibc_lending_line-of-credit_231437"


def test_parser_handles_usd_balance_without_dollar_sign(tmp_path: Path) -> None:
    snapshot = tmp_path / "page-2026-03-09T13-41-37-713Z.yml"
    snapshot.write_text(
        "\n".join(
            [
                '- heading "Deposit Accounts" [level=2] [ref=e1]',
                '- heading "Other" [level=3] [ref=e2]',
                '- generic [ref=e3]: 04492-91-05190',
                '- paragraph [ref=e4]: USD 14,544.41',
            ]
        ),
        encoding="utf-8",
    )

    accounts = CibcSnapshotParser().parse_accounts(snapshot)

    assert len(accounts) == 1
    assert accounts[0].currency == "USD"
    assert accounts[0].balance == "14544.41"


def test_parser_extracts_statement_entries(tmp_path: Path) -> None:
    snapshot = tmp_path / "page-2026-03-09T13-50-01-422Z.yml"
    snapshot.write_text(
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

    entries = CibcSnapshotParser().parse_statement_entries(
        snapshot,
        account_id="cibc_deposit_chequing_265631",
    )

    assert len(entries) == 2
    assert entries[0].month == "2026-02"
    assert entries[0].route == "#/statements/doc-1"


def test_parser_extracts_statement_account_refs(tmp_path: Path) -> None:
    snapshot = tmp_path / "page-accounts.yml"
    snapshot.write_text(
        "\n".join(
            [
                '- link "Chequing . 8265631" [ref=e26] [cursor=pointer]:',
                '  - /url: "#/statements/doc-a"',
                '- link "Line of Credit . ***1437" [ref=e61] [cursor=pointer]:',
                '  - /url: "#/statements/doc-b"',
            ]
        ),
        encoding="utf-8",
    )

    refs = CibcSnapshotParser().parse_statement_account_refs(snapshot)

    assert len(refs) == 2
    assert refs[0].account_type == "Chequing"
    assert refs[0].visible_number == "8265631"
    assert refs[0].ref == "e26"
    assert refs[1].visible_number == "***1437"
