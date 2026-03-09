# Assistant Ops

`assistant-ops` is a production-oriented MCP server scaffold for a Mac-hosted personal assistant.

It is designed around four constraints:

- secrets stay out of the repo and out of model memory
- local runtime state stays outside publishable source files
- browser automation remains supervised and auditable
- integrations are replaceable behind narrow provider interfaces

## What It Includes

- MCP server entrypoint
- approval-token gating for sensitive tools
- audit logging
- Google API-backed Gmail and Google Calendar providers when configured
- JSON-backed email and calendar demo providers as fallback
- macOS Keychain-backed credential retrieval
- Google OAuth bootstrap with Keychain refresh-token storage
- Playwright-driven CIBC browser automation
- live CIBC account, mortgage, and statement workflows

## Current CIBC Capabilities

Live-validated CIBC features in this repo:

- automatic sign-in using macOS Keychain credentials
- authenticated session reuse when a CIBC browser session is already active
- account listing from the CIBC home page
- balance extraction for deposit, lending, investment, and mortgage accounts visible on the home page
- account-statement discovery from `My Documents`
- real PDF statement download for supported statement-list flows
- mortgage detail-page navigation
- mortgage annual-summary access through the mortgage `View:` selector

Currently exposed as MCP tools:

- `list_cibc_accounts`
- `get_cibc_account_balance`
- `list_cibc_statements`
- `download_cibc_statement`
- `open_cibc_login`
- `auto_sign_in_cibc`
- `open_cibc_my_documents`
- `open_cibc_account_statements`
- `capture_cibc_session_snapshot`
- `capture_cibc_account_statements_snapshot`

Available in the code path today but not yet promoted to dedicated MCP tools:

- mortgage detail-page inspection
- mortgage annual-summary inspection
- retrieval of annual values such as `Interest Paid` from the mortgage annual summary page

## Repository Layout

```text
assistant_ops/
  src/assistant_ops/
  tests/
  docs/
  assistant_setup_design.md
  production_architecture.md
  pyproject.toml
```

Local runtime state is created under workspace-managed directories such as `data/`, `output/`, `.playwright-cli/`, and `config/integrations.json`. Those paths are ignored from source control.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .[dev]
```

Choose a workspace directory and initialize it:

```bash
export WORKSPACE="$PWD"
assistant-ops-init --workspace "$WORKSPACE"
```

Run tests:

```bash
python3 -m pytest
```

Run the MCP server:

```bash
assistant-ops-mcp --workspace "$WORKSPACE" --transport stdio
```

## Keychain Setup

Store the actual secrets in macOS Keychain:

```bash
security add-generic-password -U -s assistant-ops.cibc -a card-number -w 'YOUR_CARD_NUMBER'
security add-generic-password -U -s assistant-ops.cibc -a password -w 'YOUR_PASSWORD'
```

Write the local non-secret integration mapping:

```bash
assistant-ops-configure-keychain \
  --workspace "$WORKSPACE" \
  --cibc-card-number-service assistant-ops.cibc \
  --cibc-card-number-account card-number \
  --cibc-password-service assistant-ops.cibc \
  --cibc-password-account password
```

Generated file:

```text
$WORKSPACE/config/integrations.json
```

Example contents:

```json
{
  "cibc": {
    "card_number_service": "assistant-ops.cibc",
    "card_number_account": "card-number",
    "password_service": "assistant-ops.cibc",
    "password_account": "password"
  }
}
```

## Google OAuth Bootstrap

Google integration is implemented for Gmail and Google Calendar, with local OAuth bootstrap and Keychain-backed refresh-token storage.

Live-validated Google features in this repo:

- Gmail thread listing against a real mailbox
- Gmail draft reply creation against a real thread
- Google Calendar event listing against a real calendar
- Google Calendar event creation against a real calendar
- OAuth callback, token exchange, and Keychain refresh-token persistence on macOS
- explicit TLS CA-bundle handling for Google HTTPS calls on Macs with incomplete Python certificate stores

Current Google features:

- Google OAuth desktop-flow bootstrap CLI
- loopback callback handling
- authorization URL generation
- access-token / refresh-token exchange
- Keychain refresh-token storage
- local non-secret Google integration mapping
- Gmail thread listing
- Gmail draft reply creation
- Gmail draft send
- Google Calendar event listing
- Google Calendar event creation

Preferred setup uses local config plus Keychain.

Store the Google OAuth client secret in Keychain:

```bash
security add-generic-password -U -s assistant-ops.google -a client-secret -w 'YOUR_GOOGLE_CLIENT_SECRET'
```

Write the non-secret Google config:

```bash
assistant-ops-configure-google \
  --workspace "$WORKSPACE" \
  --google-client-id 'your-client-id.apps.googleusercontent.com' \
  --google-oauth-port 8765 \
  --google-client-secret-service assistant-ops.google \
  --google-client-secret-account client-secret \
  --google-refresh-token-service assistant-ops.google \
  --google-refresh-token-account refresh-token
```

Optional environment-variable fallback:

```bash
export ASSISTANT_OPS_GOOGLE_CLIENT_ID='your-google-client-id'
export ASSISTANT_OPS_GOOGLE_OAUTH_PORT='8765'
```

Bootstrap command:

```bash
assistant-ops-google-auth --workspace "$WORKSPACE"
```

This stores the Google refresh-token location in `config/integrations.json` and writes the actual refresh token to macOS Keychain.

Once configured, the existing MCP tools automatically use Google APIs:

- `list_email_threads`
- `draft_email_reply`
- `send_email`
- `list_calendar_events`
- `create_calendar_event`

## Runtime Configuration

Optional environment overrides:

- `ASSISTANT_OPS_PWCLI_PATH`
  Use a custom Playwright CLI wrapper or binary path.
- `ASSISTANT_OPS_SECURITY_PATH`
  Override the macOS `security` binary path.
- `ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION`
  Override the browser session name used for CIBC flows.
- `ASSISTANT_OPS_GOOGLE_CLIENT_ID`
  Google OAuth client ID for Gmail and Calendar.
- `ASSISTANT_OPS_GOOGLE_OAUTH_PORT`
  Loopback OAuth callback port for the bootstrap flow.

If `ASSISTANT_OPS_PWCLI_PATH` is not set, the app uses the bundled Codex Playwright wrapper when present and falls back to `playwright-cli` on `PATH`.

## Current Tool Surface

- `create_approval_request`
- `list_email_threads`
- `draft_email_reply`
- `send_email`
- `list_calendar_events`
- `create_calendar_event`
- `download_statement`
- `list_cibc_accounts`
- `get_cibc_account_balance`
- `list_cibc_statements`
- `download_cibc_statement`
- `open_cibc_login`
- `auto_sign_in_cibc`
- `open_cibc_my_documents`
- `open_cibc_account_statements`
- `capture_cibc_session_snapshot`
- `capture_cibc_account_statements_snapshot`
- `list_recent_actions`

## Development Docs

- [Deployment Guide](docs/DEPLOYMENT.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Google Integration Plan](docs/GOOGLE_INTEGRATION_PLAN.md)
- [Google Setup Guide](docs/GOOGLE_SETUP.md)
- [Local Setup Design](assistant_setup_design.md)
- [Production Architecture](production_architecture.md)

## Current Boundary

Implemented:

- local MCP service scaffold
- provider-oriented service structure
- macOS Keychain-backed browser sign-in for CIBC
- live CIBC statement download for validated statement-list flows
- mortgage-detail and mortgage annual-summary browser flows validated against a live CIBC session
- live Gmail read and draft creation via Google APIs
- live Google Calendar read and event creation via Google APIs

Still needed for broader production use:

- safer first-class new outbound email drafting instead of reply-only send flows
- event update/delete coverage if Calendar lifecycle management is needed
- dedicated MCP tools for mortgage-specific reads such as annual interest and tax-history extraction
- more banking providers and broader account-type coverage
- transport-level MCP client integration tests
