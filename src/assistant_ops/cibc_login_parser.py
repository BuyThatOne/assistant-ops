from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CardStepRefs:
    card_number_ref: str
    continue_ref: str
    cookie_close_ref: str | None = None


@dataclass(frozen=True)
class PasswordStepRefs:
    password_ref: str
    submit_ref: str
    cookie_close_ref: str | None = None


class CibcLoginSnapshotParser:
    def parse_public_login(self, snapshot_path: Path) -> str:
        return self._extract_ref(
            snapshot_path.read_text(encoding="utf-8"),
            r'button "Sign on to CIBC Online Banking\." \[ref=(?P<ref>e\d+)\]',
        )

    def parse_card_step(self, snapshot_path: Path) -> CardStepRefs:
        text = snapshot_path.read_text(encoding="utf-8")
        return CardStepRefs(
            card_number_ref=self._extract_ref(text, r'textbox "Card number" \[ref=(?P<ref>e\d+)\]'),
            continue_ref=self._extract_ref(text, r'button "Continue" \[ref=(?P<ref>e\d+)\]'),
            cookie_close_ref=self._maybe_extract_ref(text, r'button "Close" \[ref=(?P<ref>e\d+)\]'),
        )

    def parse_password_step(self, snapshot_path: Path) -> PasswordStepRefs:
        text = snapshot_path.read_text(encoding="utf-8")
        return PasswordStepRefs(
            password_ref=self._extract_ref(
                text,
                r'(textbox|input) "Password[^"]*" \[ref=(?P<ref>e\d+)\]',
            ),
            submit_ref=self._extract_ref(
                text,
                r'button "(Sign on|Sign On|Continue)" \[ref=(?P<ref>e\d+)\]',
            ),
            cookie_close_ref=self._maybe_extract_ref(text, r'button "Close" \[ref=(?P<ref>e\d+)\]'),
        )

    def indicates_mfa_challenge(self, snapshot_path: Path) -> bool:
        text = snapshot_path.read_text(encoding="utf-8").lower()
        indicators = (
            "verification code",
            "security code",
            "one-time passcode",
            "one time passcode",
            "one-time code",
            "one time code",
            "text me a code",
            "send a code",
            "enter the code",
            "two-step verification",
            "2-step verification",
        )
        return any(indicator in text for indicator in indicators)

    def _extract_ref(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"Could not find ref for pattern: {pattern}")
        return match.group("ref")

    def _maybe_extract_ref(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group("ref") if match else None
