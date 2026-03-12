from __future__ import annotations

from dataclasses import dataclass

from assistant_ops.models import ActionRisk


@dataclass(frozen=True)
class PolicyDecision:
    tool_name: str
    risk: ActionRisk
    approval_required: bool


class PolicyEngine:
    """Simple policy map for the first production slice."""

    _READ_ONLY_TOOLS = frozenset(
        {
            "list_email_threads",
            "search_email_threads",
            "get_email_thread",
            "draft_email_reply",
            "list_calendar_events",
            "download_statement",
            "list_cibc_accounts",
            "get_cibc_account_balance",
            "list_cibc_statements",
            "download_cibc_statement",
            "open_cibc_login",
            "open_cibc_my_documents",
            "open_cibc_account_statements",
            "capture_cibc_session_snapshot",
            "capture_cibc_account_statements_snapshot",
            "auto_sign_in_cibc",
            "list_recent_actions",
        }
    )
    _WRITE_TOOLS = frozenset({"send_email", "create_calendar_event", "update_calendar_event", "delete_calendar_event"})

    def evaluate(self, tool_name: str) -> PolicyDecision:
        if tool_name in self._READ_ONLY_TOOLS:
            return PolicyDecision(
                tool_name=tool_name,
                risk=ActionRisk.READ,
                approval_required=False,
            )

        if tool_name in self._WRITE_TOOLS:
            return PolicyDecision(
                tool_name=tool_name,
                risk=ActionRisk.WRITE,
                approval_required=True,
            )

        raise KeyError(f"Unknown tool policy: {tool_name}")
