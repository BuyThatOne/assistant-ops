from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from assistant_ops.approvals import ApprovalStore
from assistant_ops.models import ApprovalStatus


def test_approval_can_be_consumed_once(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "approvals.json")
    approval = store.create(action="send_email", target="draft_1")

    consumed = store.consume(approval.approval_id, expected_action="send_email")

    assert consumed.status == ApprovalStatus.CONSUMED
    with pytest.raises(ValueError, match="already consumed"):
        store.consume(approval.approval_id, expected_action="send_email")


def test_approval_expires_when_looked_up(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "approvals_expire.json")
    approval = store.create(action="send_email", target="draft_1")
    store._requests[approval.approval_id] = approval.model_copy(  # noqa: SLF001
        update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    store._flush()  # noqa: SLF001

    expired = store.get(approval.approval_id)

    assert expired is not None
    assert expired.status == ApprovalStatus.EXPIRED
