from assistant_ops.models import ActionRisk
from assistant_ops.policy import PolicyEngine


def test_read_only_tool_policy() -> None:
    decision = PolicyEngine().evaluate("list_email_threads")

    assert decision.risk == ActionRisk.READ
    assert decision.approval_required is False


def test_write_tool_requires_approval() -> None:
    decision = PolicyEngine().evaluate("send_email")

    assert decision.risk == ActionRisk.WRITE
    assert decision.approval_required is True


def test_cibc_tools_are_read_only() -> None:
    decision = PolicyEngine().evaluate("list_cibc_accounts")

    assert decision.risk == ActionRisk.READ
    assert decision.approval_required is False


def test_cibc_statements_tool_is_read_only() -> None:
    decision = PolicyEngine().evaluate("list_cibc_statements")

    assert decision.risk == ActionRisk.READ
    assert decision.approval_required is False


def test_email_search_tool_is_read_only() -> None:
    decision = PolicyEngine().evaluate("search_email_threads")

    assert decision.risk == ActionRisk.READ
    assert decision.approval_required is False


def test_calendar_update_requires_approval() -> None:
    decision = PolicyEngine().evaluate("update_calendar_event")

    assert decision.risk == ActionRisk.WRITE
    assert decision.approval_required is True
