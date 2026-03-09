from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from assistant_ops.models import BankAccount, StatementEntry


SECTION_MAP = {
    "Deposit Accounts": "deposit",
    "Lending Accounts": "lending",
    "Investments": "investment",
    "Credit Cards": "credit-card",
}


@dataclass(frozen=True)
class StatementAccountRef:
    account_type: str
    visible_number: str
    ref: str
    route: str | None = None


@dataclass(frozen=True)
class StatementDownloadRef:
    label: str
    month: str
    ref: str
    route: str | None = None


class CibcSnapshotParser:
    def parse_accounts(self, snapshot_path: Path) -> list[BankAccount]:
        lines = snapshot_path.read_text(encoding="utf-8").splitlines()
        current_section: str | None = None
        current_name: str | None = None
        current_number: str | None = None
        accounts: list[BankAccount] = []

        for raw_line in lines:
            line = raw_line.strip()

            section_match = re.match(r'- heading "(?P<section>.+)" \[level=2\]', line)
            if section_match:
                section = section_match.group("section")
                current_section = SECTION_MAP.get(section)
                current_name = None
                current_number = None
                continue

            if current_section is None:
                continue

            if line.startswith('- heading "') and '[level=3]' in line:
                name = re.search(r'- heading "(?P<name>.+)" \[level=3\]', line)
                if name:
                    current_name = name.group("name")
                    current_number = None
                continue

            if current_name is None:
                continue

            if current_number is None:
                number_match = re.match(r'- generic \[ref=.*\]: (?P<number>[0-9.\-]+)$', line)
                if number_match:
                    current_number = number_match.group("number")
                continue

            balance_match = re.match(
                r'- paragraph \[ref=.*\]: (?P<balance>(USD )?[0-9$,]+\.[0-9]{2})$',
                line,
            )
            if balance_match:
                balance = balance_match.group("balance")
                currency = "USD" if balance.startswith("USD ") else "CAD"
                normalized_balance = balance.replace("USD ", "").replace("$", "").replace(",", "")
                account_id = self._account_id(current_section, current_name, current_number)
                accounts.append(
                    BankAccount(
                        account_id=account_id,
                        institution="CIBC",
                        account_type=current_name,
                        currency=currency,
                        balance=normalized_balance,
                        available_balance=normalized_balance if current_section == "deposit" else None,
                    )
                )
                current_name = None
                current_number = None

        return accounts

    def _account_id(self, section: str, name: str, number: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        suffix = re.sub(r"[^0-9a-z]+", "", number.lower())[-6:]
        return f"cibc_{section}_{slug}_{suffix}"

    def parse_statement_entries(self, snapshot_path: Path, *, account_id: str) -> list[StatementEntry]:
        lines = snapshot_path.read_text(encoding="utf-8").splitlines()
        entries: list[StatementEntry] = []

        for raw_line in lines:
            line = raw_line.strip()
            route_match = re.match(r'- /url: "(?P<route>#.+)"$', line)
            if route_match and entries and entries[-1].route is None:
                entries[-1] = entries[-1].model_copy(update={"route": route_match.group("route")})
                continue

            route_match = re.match(r'- /url: (?P<route>#.+)$', line)
            if route_match and entries and entries[-1].route is None:
                entries[-1] = entries[-1].model_copy(update={"route": route_match.group("route")})
                continue

            label_match = re.match(r'- link "(?P<label>[A-Za-z]+ [0-9]+ to [A-Za-z0-9, ]+)"', line)
            if label_match:
                label = label_match.group("label")
                entries.append(
                    StatementEntry(
                        account_id=account_id,
                        label=label,
                        month=self._normalize_statement_month(label),
                        route=None,
                    )
                )

        return entries

    def parse_statement_account_refs(self, snapshot_path: Path) -> list[StatementAccountRef]:
        lines = snapshot_path.read_text(encoding="utf-8").splitlines()
        refs: list[StatementAccountRef] = []

        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            match = re.match(
                r'- link "(?P<account_type>.+?) \. (?P<number>[^"]+)" \[ref=(?P<ref>e\d+)\]',
                line,
            )
            if not match:
                continue

            route = None
            for offset in range(1, 4):
                if index + offset >= len(lines):
                    break
                route_line = lines[index + offset].strip()
                route_match = re.match(r'- /url: "(?P<route>#.+)"$', route_line)
                if route_match:
                    route = route_match.group("route")
                    break

            refs.append(
                StatementAccountRef(
                    account_type=match.group("account_type"),
                    visible_number=match.group("number"),
                    ref=match.group("ref"),
                    route=route,
                )
            )

        return refs

    def parse_statement_download_refs(self, snapshot_path: Path) -> list[StatementDownloadRef]:
        lines = snapshot_path.read_text(encoding="utf-8").splitlines()
        refs: list[StatementDownloadRef] = []

        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            match = re.match(r'- link "(?P<label>[A-Za-z]+ [0-9]+ to [A-Za-z0-9, ]+)" \[ref=(?P<ref>e\d+)\]', line)
            if not match:
                continue

            route = None
            for offset in range(1, 4):
                if index + offset >= len(lines):
                    break
                route_line = lines[index + offset].strip()
                route_match = re.match(r'- /url: "(?P<route>#.+)"$', route_line)
                if route_match:
                    route = route_match.group("route")
                    break

            label = match.group("label")
            refs.append(
                StatementDownloadRef(
                    label=label,
                    month=self._normalize_statement_month(label),
                    ref=match.group("ref"),
                    route=route,
                )
            )

        return refs

    def _normalize_statement_month(self, label: str) -> str:
        month_name = re.match(r"(?P<month>[A-Za-z]+)", label).group("month")
        year = re.search(r", (?P<year>[0-9]{4})$", label).group("year")
        month_map = {
            "January": "01",
            "February": "02",
            "March": "03",
            "April": "04",
            "May": "05",
            "June": "06",
            "July": "07",
            "August": "08",
            "September": "09",
            "October": "10",
            "November": "11",
            "December": "12",
        }
        return f"{year}-{month_map[month_name]}"
