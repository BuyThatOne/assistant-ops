from __future__ import annotations

import argparse
import json
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from assistant_ops.config import Settings
from assistant_ops.credentials import MacOSKeychainCredentialProvider
from assistant_ops.integrations import configure_google_keychain
from assistant_ops.tls import build_ssl_context


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
)


@dataclass(frozen=True)
class GoogleOAuthTokens:
    access_token: str
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    scope: str | None = None


def build_google_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    state: str,
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


def exchange_google_oauth_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> GoogleOAuthTokens:
    payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, context=build_ssl_context()) as response:  # noqa: S310
        parsed = json.loads(response.read().decode("utf-8"))
    return GoogleOAuthTokens(
        access_token=parsed["access_token"],
        refresh_token=parsed.get("refresh_token"),
        token_type=parsed.get("token_type"),
        expires_in=parsed.get("expires_in"),
        scope=parsed.get("scope"),
    )


def wait_for_google_oauth_code(*, port: int, expected_state: str, timeout_seconds: int = 300) -> str:
    result: dict[str, str] = {}
    event = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if params.get("state", [""])[0] != expected_state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid OAuth state.")
                return
            if "code" not in params:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing authorization code.")
                return

            result["code"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Google authorization completed. You can close this window.")
            event.set()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = timeout_seconds
    try:
        worker = threading.Thread(target=server.handle_request, daemon=True)
        worker.start()
        if not event.wait(timeout=timeout_seconds):
            raise TimeoutError("Timed out waiting for Google OAuth callback.")
    finally:
        server.server_close()
    return result["code"]


def bootstrap_google_oauth(
    *,
    workspace_root: Path,
    client_id: str,
    client_secret: str,
    oauth_port: int,
    client_secret_service: str,
    client_secret_account: str,
    refresh_token_service: str,
    refresh_token_account: str,
    open_browser: bool = True,
) -> dict[str, str]:
    redirect_uri = f"http://127.0.0.1:{oauth_port}/callback"
    state = secrets.token_urlsafe(24)
    auth_url = build_google_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=DEFAULT_SCOPES,
        state=state,
    )
    if open_browser:
        webbrowser.open(auth_url)

    code = wait_for_google_oauth_code(port=oauth_port, expected_state=state)
    tokens = exchange_google_oauth_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    if not tokens.refresh_token:
        raise RuntimeError("Google OAuth flow did not return a refresh token.")

    settings = Settings.for_workspace(workspace_root)
    keychain = MacOSKeychainCredentialProvider(security_path=settings.security_path)
    keychain.write(
        service=refresh_token_service,
        account=refresh_token_account,
        secret=tokens.refresh_token,
    )
    configure_google_keychain(
        workspace_root,
        client_id=client_id,
        oauth_port=oauth_port,
        client_secret_service=client_secret_service,
        client_secret_account=client_secret_account,
        refresh_token_service=refresh_token_service,
        refresh_token_account=refresh_token_account,
    )
    return {
        "status": "configured",
        "client_id": client_id,
        "oauth_port": str(oauth_port),
        "client_secret_service": client_secret_service,
        "client_secret_account": client_secret_account,
        "refresh_token_service": refresh_token_service,
        "refresh_token_account": refresh_token_account,
        "redirect_uri": redirect_uri,
        "authorization_url": auth_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Google OAuth bootstrap and store the refresh token in Keychain.")
    parser.add_argument("--workspace", default=".", help="Workspace root to configure.")
    parser.add_argument("--client-id", help="Google OAuth client ID. Falls back to config, then ASSISTANT_OPS_GOOGLE_CLIENT_ID.")
    parser.add_argument("--client-secret", help="Google OAuth client secret. Overrides Keychain lookup if provided.")
    parser.add_argument("--oauth-port", type=int, help="Loopback OAuth callback port. Falls back to config, then ASSISTANT_OPS_GOOGLE_OAUTH_PORT.")
    parser.add_argument("--client-secret-service", default="assistant-ops.google", help="Keychain service for the Google OAuth client secret.")
    parser.add_argument("--client-secret-account", default="client-secret", help="Keychain account for the Google OAuth client secret.")
    parser.add_argument("--refresh-token-service", default="assistant-ops.google", help="Keychain service for the Google refresh token.")
    parser.add_argument("--refresh-token-account", default="refresh-token", help="Keychain account for the Google refresh token.")
    parser.add_argument("--no-open-browser", action="store_true", help="Do not auto-open the authorization URL.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace).resolve()
    settings = Settings.for_workspace(workspace_root)
    client_id = args.client_id or settings.google_client_id
    oauth_port = args.oauth_port or settings.google_oauth_port
    client_secret_service = args.client_secret_service or settings.google_client_secret_service
    client_secret_account = args.client_secret_account or settings.google_client_secret_account
    keychain = MacOSKeychainCredentialProvider(security_path=settings.security_path)
    client_secret = args.client_secret
    if client_secret is None and client_secret_service and client_secret_account:
        client_secret = keychain.read(
            service=client_secret_service,
            account=client_secret_account,
        )

    if not client_id or not client_secret:
        raise RuntimeError(
            "Google OAuth client ID/secret are required. Use --client-id/--client-secret, "
            "configure the client secret in Keychain, or set ASSISTANT_OPS_GOOGLE_CLIENT_ID."
        )

    if args.client_secret:
        keychain.write(
            service=client_secret_service,
            account=client_secret_account,
            secret=args.client_secret,
        )

    result = bootstrap_google_oauth(
        workspace_root=workspace_root,
        client_id=client_id,
        client_secret=client_secret,
        oauth_port=oauth_port,
        client_secret_service=client_secret_service,
        client_secret_account=client_secret_account,
        refresh_token_service=args.refresh_token_service,
        refresh_token_account=args.refresh_token_account,
        open_browser=not args.no_open_browser,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
