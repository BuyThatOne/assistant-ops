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
- JSON-backed demo providers for email and calendar
- macOS Keychain-backed credential retrieval
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

## Runtime Configuration

Optional environment overrides:

- `ASSISTANT_OPS_PWCLI_PATH`
  Use a custom Playwright CLI wrapper or binary path.
- `ASSISTANT_OPS_SECURITY_PATH`
  Override the macOS `security` binary path.
- `ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION`
  Override the browser session name used for CIBC flows.

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
- [Local Setup Design](assistant_setup_design.md)
- [Production Architecture](production_architecture.md)

## Current Boundary

Implemented:

- local MCP service scaffold
- provider-oriented service structure
- macOS Keychain-backed browser sign-in for CIBC
- live CIBC statement download for validated statement-list flows
- mortgage-detail and mortgage annual-summary browser flows have been validated against a live CIBC session

Still needed for broader production use:

- real email provider adapter
- real calendar provider adapter
- dedicated MCP tools for mortgage-specific reads such as annual interest and tax-history extraction
- more banking providers and broader account-type coverage
- transport-level MCP client integration tests
