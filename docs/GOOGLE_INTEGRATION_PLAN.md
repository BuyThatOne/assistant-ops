# Gmail and Google Calendar Implementation Plan

## Status

Implemented and live-validated on macOS:

- Google OAuth desktop bootstrap
- Keychain-backed Google client secret lookup
- Keychain-backed refresh-token storage
- Gmail thread listing
- Gmail draft reply creation
- Google Calendar event listing
- Google Calendar event creation

Implemented and test-covered but not live-validated by default:

- Gmail draft send against an existing thread

## Objective

Add production-grade Gmail and Google Calendar support to `assistant-ops` using Google APIs, OAuth 2.0, and macOS Keychain-backed token storage.

This plan assumes:

- API-first integration
- browser automation only as fallback
- no raw Google credentials stored in repo files
- portable deployment to other Mac hosts

## Recommended Access Model

Use Google APIs directly:

- Gmail API for mailbox reads, draft creation, and send operations
- Google Calendar API for event reads, create/update flows, and availability queries

Use OAuth 2.0 desktop-app flow:

- user signs in through Google once
- app receives access token and refresh token
- refresh token is stored in macOS Keychain
- workspace stores only non-secret configuration

Do not use:

- Gmail or Calendar UI automation as the primary path
- plaintext token files
- service accounts for personal Gmail unless there is a specific Google Workspace admin use case

## Scope

### Phase 1: Foundation

- add Google integration config model
- add Google OAuth client configuration handling
- add Keychain-backed refresh-token storage and retrieval
- add generic HTTP client boundary for Google APIs
- add portable environment/runtime configuration for Google integration

### Phase 2: Gmail Read and Draft

- list recent Gmail threads
- fetch thread metadata and message snippets
- draft reply without sending
- preserve current approval model for sends

### Phase 3: Gmail Send

- send drafted Gmail messages
- require approval token for send
- record audit log entries for draft and send actions

### Phase 4: Google Calendar Read and Write

- list events for a day or date range
- create event
- optionally update event in later phase
- require approval for writes

### Phase 5: Production Hardening

- retry logic and Google API error mapping
- refresh-token renewal path
- config validation and setup checks
- integration documentation for fresh Mac hosts

## Architecture Changes

## 1. Config

Extend `src/assistant_ops/config.py` with Google-specific runtime settings.

Add support for:

- OAuth client ID
- OAuth client secret reference or client JSON path
- redirect URI or loopback callback port
- Keychain service/account identifiers for refresh token storage

Optional environment-variable fallbacks:

- `ASSISTANT_OPS_GOOGLE_CLIENT_ID`
- `ASSISTANT_OPS_GOOGLE_OAUTH_PORT`

Workspace config should store only non-secret identifiers. The preferred production path is local config plus Keychain, not env vars for secrets.

## 2. Credentials and Token Storage

Extend `src/assistant_ops/credentials.py` or add a token store module for:

- writing Google refresh token to macOS Keychain
- reading Google refresh token from macOS Keychain
- optionally deleting/rotating token entries

Suggested Keychain naming:

- service: `assistant-ops.google`
- account: `refresh-token`

Do not store:

- access tokens on disk
- refresh tokens in `config/`
- client secret in committed files

## 3. Google API Client Layer

Add a new module, for example:

- `src/assistant_ops/google_auth.py`
- `src/assistant_ops/google_client.py`

Responsibilities:

- exchange authorization code for tokens
- refresh access tokens
- attach bearer tokens to Gmail and Calendar requests
- normalize Google API errors into application-level exceptions

## 4. Provider Interfaces

Extend provider boundaries in `src/assistant_ops/adapters.py`.

Add concrete providers such as:

- `GoogleGmailProvider`
- `GoogleCalendarProvider`

Keep existing provider protocols small and explicit.

Gmail provider methods should cover:

- `list_threads(limit)`
- `get_thread(thread_id)`
- `draft_reply(thread_id, body)`
- `send_draft(draft_id)`

Calendar provider methods should cover:

- `list_events(day_or_range)`
- `create_event(...)`

## 5. MCP Tool Surface

Retain current tool names where possible and swap provider implementations under the hood.

Likely outcome:

- `list_email_threads` uses Gmail API instead of JSON demo data
- `draft_email_reply` uses Gmail drafts
- `send_email` sends Gmail draft with approval token
- `list_calendar_events` uses Google Calendar
- `create_calendar_event` creates Google event with approval token

Add setup tools only if necessary. Prefer separate CLI setup commands over exposing OAuth setup directly as routine MCP tools.

## OAuth Flow Plan

## 1. Initial Setup Command

Add a CLI command such as:

- `assistant-ops-google-auth`

Responsibilities:

- start a local loopback server
- open Google consent screen in browser
- receive authorization code
- exchange code for refresh token
- store refresh token in Keychain
- write any non-secret identifiers to workspace config

## 2. Scopes

Start with minimal scopes.

Recommended first pass:

- Gmail read:
  - `https://www.googleapis.com/auth/gmail.readonly`
- Gmail draft/send:
  - `https://www.googleapis.com/auth/gmail.compose`
  - `https://www.googleapis.com/auth/gmail.send`
- Calendar:
  - `https://www.googleapis.com/auth/calendar`

If you want stricter separation, split read-only and write-capable auth profiles later.

## 3. Token Refresh

At runtime:

- read refresh token from Keychain
- exchange for access token as needed
- keep access token in memory only

## Test Plan

## Unit Tests

Add tests for:

- config loading for Google settings
- Keychain token-store behavior behind a fake runner
- OAuth token parsing and refresh logic
- Gmail provider response mapping
- Calendar provider response mapping
- policy enforcement on Gmail send and Calendar create

## Service Tests

Add service-level tests for:

- `list_email_threads`
- `draft_email_reply`
- `send_email`
- `list_calendar_events`
- `create_calendar_event`

These should use fake Google clients, not live Google accounts.

## Integration Tests

Do not require live Google access in CI.

Optional operator-run integration checks:

- successful OAuth bootstrap
- Gmail read flow
- Gmail draft flow
- Calendar read flow
- Calendar create flow against a test calendar

## Documentation Deliverables

Add or update:

- `README.md`
  include Google capabilities and setup overview
- `docs/DEPLOYMENT.md`
  include Google Cloud project setup and Mac host deployment steps
- `docs/DEVELOPMENT.md`
  include provider extension notes for Google APIs

Optionally add:

- `docs/GOOGLE_SETUP.md`
  step-by-step Google Cloud console instructions

## Execution Order

1. Add config and token-storage primitives.
2. Add Google auth module and CLI bootstrap flow.
3. Implement Gmail provider.
4. Implement Calendar provider.
5. Swap server wiring from JSON demo providers to Google providers behind config gates.
6. Add tests for config, auth, providers, and services.
7. Update docs.
8. Run full test suite.

## Open Design Decisions

These should be decided before implementation starts:

1. Whether to support one Google account only or multiple named Google accounts.
2. Whether Gmail send and Calendar write should share the same OAuth token or use separate scope grants.
3. Whether Google client credentials should be supplied via environment variables or a local untracked config file.
4. Whether to expose dedicated Gmail thread-detail and Calendar update/delete tools in the first release.

## Recommended First Milestone

Build the smallest useful API-backed slice:

- OAuth bootstrap CLI
- Keychain refresh-token storage
- Gmail thread listing
- Gmail draft creation
- Google Calendar event listing

Then add:

- Gmail send with approval
- Calendar create with approval

## Success Criteria

The Google integration is ready for first production use when:

- a fresh Mac host can authenticate without manual file editing
- no raw Google secrets are committed or stored in tracked files
- Gmail read/draft works through Google APIs in a live account
- Calendar read/create works through Google APIs in a live account
- write actions still require approval tokens
- full automated test suite passes without live Google access
