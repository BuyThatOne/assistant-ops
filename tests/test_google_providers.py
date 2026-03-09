from assistant_ops.adapters import GoogleCalendarProvider, GoogleGmailProvider


class FakeGoogleClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []

    def request_json(self, *, method: str, url: str, body: dict | None = None) -> dict:
        self.calls.append((method, url, body))
        if url.endswith("/threads?maxResults=2"):
            return {"threads": [{"id": "thr_1"}, {"id": "thr_2"}]}
        if "/threads/thr_1" in url:
            return {
                "id": "thr_1",
                "messages": [
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Quarterly package"},
                                {"name": "From", "value": "acct@example.com"},
                            ]
                        }
                    }
                ],
            }
        if "/threads/thr_2" in url:
            return {
                "id": "thr_2",
                "messages": [
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Meeting request"},
                                {"name": "From", "value": "cal@example.com"},
                            ]
                        }
                    }
                ],
            }
        if "/threads/thread-reply" in url:
            return {
                "id": "thread-reply",
                "messages": [
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Need follow-up"},
                                {"name": "From", "value": "owner@example.com"},
                                {"name": "Reply-To", "value": "reply@example.com"},
                                {"name": "Message-ID", "value": "<id@example.com>"},
                                {"name": "References", "value": "<ref@example.com>"},
                            ]
                        }
                    }
                ],
            }
        if url.endswith("/drafts"):
            return {"id": "draft-123"}
        if url.endswith("/drafts/send"):
            return {"message": {"threadId": "thread-reply"}}
        if "calendar/v3/calendars/primary/events?" in url:
            return {
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Budget review",
                        "start": {"dateTime": "2026-03-10T10:00:00-05:00"},
                        "end": {"dateTime": "2026-03-10T10:30:00-05:00"},
                    }
                ]
            }
        if url.endswith("/events"):
            return {
                "id": "evt-2",
                "summary": body["summary"],
                "start": body["start"],
                "end": body["end"],
            }
        raise AssertionError(f"Unexpected call: {(method, url, body)}")


def test_google_gmail_provider_lists_threads() -> None:
    provider = GoogleGmailProvider(client=FakeGoogleClient())

    threads = provider.list_threads(2)

    assert len(threads) == 2
    assert threads[0].thread_id == "thr_1"
    assert threads[0].subject == "Quarterly package"


def test_google_gmail_provider_creates_and_sends_draft() -> None:
    provider = GoogleGmailProvider(client=FakeGoogleClient())

    draft = provider.draft_reply("thread-reply", "Thanks, will do.")
    sent = provider.send_draft(draft.draft_id)

    assert draft.draft_id == "draft-123"
    assert draft.thread_id == "thread-reply"
    assert sent.sent is True
    assert sent.thread_id == "thread-reply"


def test_google_calendar_provider_lists_and_creates_events() -> None:
    provider = GoogleCalendarProvider(client=FakeGoogleClient())

    events = provider.list_events("2026-03-10")
    created = provider.create_event(
        "Planning review",
        "2026-03-10T13:00:00-05:00",
        "2026-03-10T13:30:00-05:00",
    )

    assert len(events) == 1
    assert events[0].event_id == "evt-1"
    assert created.event_id == "evt-2"
    assert created.title == "Planning review"
