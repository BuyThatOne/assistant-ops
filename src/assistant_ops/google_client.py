from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from assistant_ops.google_auth import TOKEN_ENDPOINT
from assistant_ops.tls import build_ssl_context


class HttpTransport(Protocol):
    def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: dict | None = None,
    ) -> dict: ...


class UrllibJsonTransport:
    def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: dict | None = None,
    ) -> dict:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers=headers or {},
            method=method,
        )
        with urlopen(request, context=build_ssl_context()) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
        return {} if not raw else json.loads(raw)


@dataclass(frozen=True)
class GoogleTokenBundle:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None


class GoogleApiClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        transport: HttpTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._transport = transport or UrllibJsonTransport()
        self._token_bundle: GoogleTokenBundle | None = None

    def request_json(
        self,
        *,
        method: str,
        url: str,
        body: dict | None = None,
    ) -> dict:
        token = self._access_token()
        return self._transport.request_json(
            method=method,
            url=url,
            headers={
                "Authorization": f"Bearer {token.access_token}",
                "Content-Type": "application/json",
            },
            body=body,
        )

    def _access_token(self) -> GoogleTokenBundle:
        if self._token_bundle is None:
            self._token_bundle = self.refresh_access_token()
        return self._token_bundle

    def refresh_access_token(self) -> GoogleTokenBundle:
        encoded = urlencode(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(
            TOKEN_ENDPOINT,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, context=build_ssl_context()) as response:  # noqa: S310
            parsed = json.loads(response.read().decode("utf-8"))
        return GoogleTokenBundle(
            access_token=parsed["access_token"],
            token_type=parsed.get("token_type", "Bearer"),
            expires_in=parsed.get("expires_in"),
        )


def build_gmail_reply_raw(
    *,
    to_address: str,
    subject: str,
    body: str,
    message_id: str | None = None,
    references: str | None = None,
) -> str:
    message = EmailMessage()
    message["To"] = to_address
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if message_id:
        message["In-Reply-To"] = message_id
    if references:
        message["References"] = references
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
