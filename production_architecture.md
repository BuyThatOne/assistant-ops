# Production Architecture for a Credentialed Personal Assistant

## Overview

This document describes a production architecture for a personal assistant system that can help with:

- email review and drafting
- calendar review and scheduling support
- accounting workflows
- retrieval of data from credentialed websites
- browser automation for systems without usable APIs

The design goal is to support production use without making the model itself the security boundary.

## Executive Recommendation

The best production form is:

- `MCP server` as the primary control plane
- `skill` as the workflow and policy layer for the model
- `scripts` as deterministic helpers behind the MCP server

This is the recommended split because:

- the `MCP server` provides stable tools, policy enforcement, secret access mediation, audit logging, and approval gates
- the `skill` tells the model how to use those tools safely and consistently
- the `scripts` handle narrow repeatable data-processing tasks without embedding system policy into prompt instructions

Do not use a skill alone or browser automation alone as the production architecture.

## Goals

- keep credentials out of model context whenever possible
- isolate secrets, sessions, and privileged actions behind a controllable service boundary
- support both API-native and browser-native integrations
- enforce confirmation for high-risk actions
- maintain auditability of tool usage and external side effects
- make the system extensible without redesigning the trust model

## Non-Goals

- allowing fully autonomous financial actions without a human approval step
- storing all secrets directly in prompts, repo files, or model memory
- treating browser automation as the only integration strategy

## Design Principles

1. The model is not the root of trust.
2. Secrets should be resolved just-in-time by controlled infrastructure.
3. Prefer official APIs over browser automation.
4. Use browser automation only where APIs are unavailable or inadequate.
5. Every high-risk action must have an approval boundary.
6. Every privileged action should be auditable.
7. The system should degrade safely to read-only behavior when uncertain.

## High-Level Architecture

```text
User
  |
  v
Codex / LLM Runtime
  |
  v
Skill Layer
  |
  v
MCP Server
  |
  +--> Secret Provider (macOS Keychain / cloud secret manager)
  +--> Email/Calendar APIs
  +--> Accounting / Finance APIs
  +--> Browser Automation Worker
  +--> Data Processing Scripts
  +--> Audit Log Store
  +--> Approval Service / Queue
```

## Component Responsibilities

### 1. Skill Layer

The skill is responsible for model behavior guidance, not for trust enforcement.

Use the skill to define:

- when to prefer API tools over browser tools
- when the assistant must ask for confirmation
- what classes of actions are read-only
- expected output formats
- fallback procedures when an integration fails

The skill should not:

- contain raw secrets
- implement authorization logic
- be the only place that sensitive-action policy exists

### 2. MCP Server

The MCP server is the core production component.

It should provide:

- a stable tool interface to the model
- authentication and authorization checks
- secret lookup and token exchange
- policy enforcement
- approval gating
- audit logging
- rate limiting and retries
- routing between APIs, scripts, and browser workers

This is the right layer to enforce:

- read-only vs write-capable tools
- account scoping
- environment separation
- which actions require approval
- which tool calls are blocked entirely

### 3. Scripts

Scripts are best for deterministic jobs.

Examples:

- normalize downloaded CSV files
- parse statements into structured records
- generate reconciliation reports
- convert exports into workbook-ready formats
- create tax or accounting summaries

Scripts should:

- accept structured input
- produce structured output
- avoid direct secret access unless mediated by the MCP server

### 4. Browser Automation Worker

A browser worker is necessary for websites that do not provide usable APIs.

It should be isolated from the model and ideally from the MCP control process.

Responsibilities:

- launch dedicated browser profiles or ephemeral sessions
- navigate sites
- download files
- capture state for audit/debugging
- continue automatically through low-risk authenticated read flows when no MFA or extra verification challenge appears
- stop for MFA, step-up verification, or sensitive write actions unless approval is present

Do not let the model interact with raw browser sessions directly without a server-side control layer in production.

## Recommended Deployment Forms

### Option A: Single-Host macOS Deployment

Best for:

- one operator
- personal operations
- local browser automation
- lower scale

Shape:

- Codex running on the Mac
- local MCP server running as a user service
- secrets in `macOS Keychain`
- browser workers using isolated local profiles
- local audit logs

Pros:

- simplest setup
- direct browser access
- lowest operational overhead

Cons:

- limited isolation
- tied to one machine
- harder to centralize policy and logging if usage expands

### Option B: Hybrid Deployment

Best for:

- one user with increasing production requirements
- need for centralized APIs and logging
- some browser tasks still requiring a Mac host

Shape:

- MCP server hosted centrally
- browser worker hosted on a managed Mac mini or dedicated desktop node
- API integrations and policy engines hosted centrally
- secrets stored in a real secret manager or macOS-native secret integration

Pros:

- better separation of concerns
- easier logging and policy evolution
- still supports browser-only sites

Cons:

- more operational complexity
- browser host remains a special-case dependency

### Option C: Fully Managed Service Architecture

Best for:

- team use
- strong compliance or audit requirements
- multiple accounts and workflows

Shape:

- central MCP service
- secret manager
- approval workflow system
- worker fleet for APIs and browser jobs
- structured event logging and monitoring

Pros:

- strongest policy enforcement
- scalable
- easiest to extend to multiple users and services

Cons:

- highest engineering cost
- browser automation for consumer sites remains operationally fragile

## Trust Boundaries

### Boundary 1: Model to MCP Server

The model may request tools.

The MCP server decides:

- whether the tool is allowed
- whether the account is in scope
- whether approval is required
- whether secrets may be resolved

### Boundary 2: MCP Server to Secret Store

The MCP server should fetch only the secret needed for the current action.

Rules:

- no bulk secret export
- secrets never returned to the model unless explicitly required and policy-approved
- short-lived tokens preferred over reusable passwords

### Boundary 3: MCP Server to External Systems

Integrations should be capability-scoped.

Examples:

- read inbox vs send email
- list calendar events vs create or delete event
- download statement vs initiate transfer

### Boundary 4: MCP Server to Browser Worker

Browser automation should operate under tightly constrained actions.

Rules:

- explicit site allowlist
- approved browser profile mapping
- no unrestricted arbitrary browsing in high-risk profiles
- write actions blocked unless an approval token is attached

## Secret Management Design

## Primary Recommendation

For a Mac-centered deployment:

- use `macOS Keychain` as the local source of truth initially
- migrate to a dedicated secret manager if central hosting expands

For a more service-oriented deployment:

- use a proper secret manager such as AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault

### Secret Categories

1. Root secrets
   - password manager credentials
   - email provider admin credentials
   - bank credentials
   - MFA recovery artifacts

2. Operational credentials
   - API tokens
   - OAuth refresh tokens
   - app passwords
   - accounting software credentials

3. Session artifacts
   - cookies
   - browser session state
   - temporary download tokens

### Rules

- prefer OAuth and delegated access over username/password
- prefer passkeys where supported
- separate recovery artifacts from active login credentials
- rotate operational credentials independently
- never store raw credentials in repo files, prompt templates, or skill text

## Tool Surface Design for the MCP Server

Expose narrow tools instead of one generic super-tool.

Recommended tool groups:

### Email Tools

- `list_email_threads`
- `get_email_thread`
- `draft_email_reply`
- `send_email`
- `archive_email_thread`

### Calendar Tools

- `list_calendar_events`
- `find_time_slots`
- `draft_calendar_invite`
- `create_calendar_event`
- `update_calendar_event`

### Accounting Tools

- `list_financial_accounts`
- `download_statement`
- `download_transaction_export`
- `categorize_transactions`
- `generate_reconciliation_report`

### Browser Tools

- `start_browser_session`
- `navigate_site`
- `download_from_site`
- `extract_page_data`
- `request_sensitive_browser_action`

### Approval Tools

- `create_approval_request`
- `check_approval_status`
- `consume_approval_token`

### Audit Tools

- `log_action`
- `list_recent_actions`
- `get_action_record`

Design rule:

Separate read tools from write tools. Do not overload a single tool with mixed capability modes.

## Approval Model

The approval model is mandatory for production.

### Actions that should require approval

- sending email
- creating or deleting calendar events on behalf of the user unless explicitly pre-authorized
- initiating payments or transfers
- changing credential or MFA settings
- granting application consent
- deleting files or records from external systems
- submitting tax or government forms

### Actions that may be pre-authorized

- reading email
- drafting unsent replies
- reading calendars
- downloading statements
- downloading transaction exports
- classifying transactions
- generating reports

### Approval Token Pattern

Recommended flow:

1. model requests a sensitive action
2. MCP server creates an approval request
3. user approves through a trusted UI
4. MCP server issues a short-lived approval token
5. only the approved action may consume that token

This is better than asking the model to remember whether approval was granted.

## Audit and Logging

Every external side effect should be logged.

Minimum log fields:

- timestamp
- user identity
- model/session identity
- tool name
- action target
- read or write classification
- approval requirement
- approval token ID if used
- result status
- artifact references such as downloaded file path

Avoid logging:

- raw passwords
- full recovery codes
- full sensitive document contents unless required by policy

## Browser Automation Strategy

Browser automation should be the fallback, not the default.

Use it when:

- the site has no API
- the API is incomplete
- the action is fundamentally browser-native

Operational recommendations:

- use dedicated browser profiles by trust level
- site allowlist by domain
- action allowlist by site
- screenshots or snapshots for audit on sensitive flows
- retry logic with bounded limits
- strong timeout and failure handling

For financial sites:

- default to read-only tasks
- require approval for any action that could move funds or change account configuration
- prefer download/export actions over page scraping when possible

## Data Processing Design

Data processing scripts should be isolated from credential handling.

Recommended pattern:

1. MCP tool downloads export or statement
2. file stored in controlled location
3. deterministic script transforms the file
4. structured output returned to the MCP layer
5. model receives only the necessary summary or derived data

Benefits:

- clearer debugging
- reduced secret exposure
- easier testing

## Environment Strategy

Use separate environments:

- `dev`
- `staging`
- `prod`

Differences by environment:

- separate secrets
- separate test accounts where possible
- separate browser profiles or worker instances
- stricter approval and logging in `prod`

Never reuse production financial credentials in development experiments.

## Security Controls

Minimum controls:

- MFA everywhere possible
- device encryption
- session expiration review
- least privilege for tools and accounts
- allowlists for domains and actions
- approval tokens for sensitive writes
- secret rotation process
- audit log retention

Recommended additional controls:

- anomaly alerts for unusual finance actions
- separate service accounts for APIs
- IP/device monitoring where providers support it
- periodic access review

## Failure Modes and Safe Degradation

If any of the following occur, the system should degrade to read-only or stop:

- approval service unavailable
- secret lookup failure
- ambiguous account mapping
- unexpected MFA challenge on a high-risk action
- browser automation divergence on a financial site
- policy engine failure

Fail-safe behavior:

- do not guess
- do not proceed with writes
- return a clear blocked status

## Recommended Build Order

### Phase 1: Core MCP Skeleton

Build:

- MCP server framework
- audit logging
- approval request model
- read-only tool structure

Deliverable:

- working MCP server with no secreted write paths

### Phase 2: API-First Integrations

Build:

- email integration
- calendar integration
- accounting/export integrations where APIs exist

Deliverable:

- read and draft workflows through APIs

### Phase 3: Browser Worker

Build:

- isolated browser worker
- site allowlist
- download flows
- session/profile management

Deliverable:

- safe browser fallback for non-API sites

### Phase 4: Sensitive Action Approval

Build:

- approval queue or UI
- short-lived approval tokens
- policy checks for write tools

Deliverable:

- production-safe write gating

### Phase 5: Script Integration

Build:

- deterministic accounting scripts
- file normalization pipeline
- report generation tools

Deliverable:

- end-to-end accounting processing without exposing secrets to scripts directly

### Phase 6: Hardening

Build:

- monitoring
- rotation procedures
- environment separation
- operator runbooks

Deliverable:

- production readiness with operational controls

## Recommended First Production Version

For your use case, the best first production version is:

- local or hybrid `MCP server`
- Keychain-backed secret resolution
- dedicated browser worker for sites without APIs
- strict read-only defaults
- approval-gated writes
- skill-based workflow guidance
- local accounting scripts behind MCP tools

This gives you the right control boundary without overbuilding too early.

## Final Recommendation

If you want one production form to optimize around, choose `MCP server`.

Then add:

- a `skill` to teach Codex the workflow and policy
- `scripts` for narrow deterministic jobs

That combination is the most defensible production architecture because it separates:

- policy from execution
- secrets from the model
- deterministic processing from orchestration
- read paths from write paths

It is the most practical structure for a real assistant that must operate across email, calendar, accounting, and credentialed websites.
