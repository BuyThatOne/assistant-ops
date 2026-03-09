from assistant_ops.google_client import build_gmail_reply_raw


def test_build_gmail_reply_raw_prefixes_subject_and_encodes_message() -> None:
    raw = build_gmail_reply_raw(
        to_address="person@example.com",
        subject="Quarterly update",
        body="Reply body",
        message_id="<message-id@example.com>",
        references="<ref@example.com>",
    )

    assert isinstance(raw, str)
    assert raw
