# Personal Assistant Credential Setup for macOS

## Overview

This document describes a secure and practical setup for using Codex as a personal assistant for:

- email triage and drafting
- calendar review and scheduling assistance
- accounting workflows such as statement retrieval, transaction export, and bookkeeping support

The design assumes work is performed on a single Mac host that you control, and that Codex may automate browser interactions locally.

## Goals

- Keep long-term credentials out of the project workspace.
- Minimize the number of secrets exposed to Codex during normal operation.
- Allow low-friction access to websites you already use.
- Reduce blast radius if the Mac, browser profile, or a single credential is compromised.
- Require explicit confirmation for high-risk actions such as money movement, password changes, or deleting records.

## Non-Goals

- Building a fully autonomous system that can move money or change account security settings without confirmation.
- Centralizing all credentials into Codex-managed storage.
- Replacing bank-native security controls, MFA, or delegated-access features.

## Threat Model

Primary risks:

- secrets stored in plaintext on disk
- browser session theft from an over-privileged profile
- accidental execution of sensitive actions by automation
- overuse of one master credential across banking, email, and business systems
- recovery codes and passwords stored together without separation

Design principle:

Codex should be an operator of authenticated sessions, not the root store of credentials.

## Recommended Architecture

### 1. Source of Truth for Secrets

Use `macOS Keychain` as the primary credential store for this Mac-hosted assistant workflow.

Why:

- native OS integration
- no separate paid subscription required
- strong local security properties on a single-user Mac
- good fit for browser-assisted banking workflows that stay on one machine

Acceptable alternative:

- `Bitwarden` if you want cross-platform sync and are comfortable managing a separate password manager

Do not use:

- plaintext files
- spreadsheets
- `.env` files in this repo
- Apple Notes for primary secret storage

### 2. macOS-Native Security Controls

Enable and enforce:

- `FileVault`
- strong Mac login password
- Touch ID for password manager unlock
- automatic screen lock after short inactivity
- separate standard user account for daily work if you currently use an admin account

Optional:

- iCloud Keychain for low-risk personal logins only

### 3. Dedicated Browser Profiles

Create separate browser profiles with different trust levels.

Recommended profiles:

- `Finance`: banking, brokerage, CRA, payment processors
- `Work Admin`: email, calendar, accounting SaaS, payroll, bookkeeping tools
- `General`: all non-sensitive browsing

Rules:

- never use the `Finance` profile for casual browsing
- keep the `Finance` and `Work Admin` profiles signed in only to required sites
- disable unnecessary extensions in sensitive profiles
- do not install developer/debug extensions in the `Finance` profile

### 4. Authentication Strategy

Prefer, in order:

1. delegated or accountant access provided by the institution
2. OAuth or passkeys
3. app-specific passwords where applicable
4. full username/password login only when no narrower option exists

For financial institutions:

- prefer read-only or limited-role access where supported
- set alerts for login, large transactions, and profile changes
- keep transfer limits low
- when a site does not use MFA, automation may continue directly after credential submission
- when a site presents an MFA or extra verification step, automation should pause for manual completion

### 5. How Codex Should Operate

Codex should generally interact with already-authenticated browser sessions.

Normal workflow:

1. you unlock the password manager and sign in to sites as needed
2. Codex uses browser automation against the relevant browser profile
3. Codex performs read, summarize, draft, export, reconcile, and navigation tasks
4. Codex stops and requests confirmation before high-risk actions

Codex should not be used as:

- the permanent storage location for credentials
- a holder of raw backup codes in chat
- an unrestricted executor for money movement

## Secret Classification

### Tier 1: Root Secrets

Examples:

- password manager master password
- Apple ID password
- primary email account password
- bank primary login credentials
- MFA recovery codes

Handling:

- stored only in password manager
- never pasted into workspace files
- never shared in bulk with Codex
- recovery codes stored separately within the password manager, tagged and access-controlled

### Tier 2: Operational Secrets

Examples:

- app-specific passwords
- OAuth refresh-capable service accounts
- bookkeeping software logins
- shipping/accounting SaaS credentials

Handling:

- store in password manager
- use smallest privilege possible
- rotate if shared or exposed during setup

### Tier 3: Session State

Examples:

- browser cookies
- authenticated tabs
- saved sessions in dedicated browser profiles

Handling:

- acceptable for Codex-driven browsing on your Mac
- isolate by browser profile
- periodically review active sessions and device lists

## Approval Policy for Sensitive Actions

Require manual confirmation for:

- initiating transfers, bill payments, wires, EFTs, or inter-account moves
- changing passwords, MFA factors, recovery settings, or trusted devices
- filing taxes or submitting government forms
- deleting emails, accounting records, or documents
- granting third-party app access

Allow automation without extra confirmation for:

- reading inboxes and labels
- drafting replies without sending unless instructed
- reviewing calendar availability
- downloading statements
- exporting transactions
- categorizing transactions
- preparing reconciliation summaries

## Storage Decisions

### Password Vault

Use `macOS Keychain` with a naming convention for service and account labels.

Suggested services:

- `assistant-ops.cibc`
- `assistant-ops.email`
- `assistant-ops.calendar`

Suggested accounts:

- `card-number`
- `password`
- `app-password`
- `oauth-refresh-token`

### Local Files

Store downloaded records in structured folders, for example:

```text
~/Documents/Operations/
  Banking/
  Accounting/
  Tax/
  Inbox-Exports/
```

Rules:

- no passwords in filenames
- no secrets in spreadsheets used for bookkeeping
- sensitive exports should have predictable locations so Codex can operate on them without re-requesting credentials

### Browser Choice

Recommended:

- `Google Chrome` or `Microsoft Edge` for profile separation and site compatibility

Alternative:

- `Safari` for personal use, but less ideal if you want repeatable automation across multiple isolated profiles

## Proposed Operating Model

### Email and Calendar

- use one dedicated `Work Admin` browser profile
- remain signed in to your main email/calendar provider
- let Codex draft but not send by default
- allow send only when you explicitly say to send

### Banking and Accounting

- use one dedicated `Finance` profile
- prefer read-only accountant or business delegate access where available
- use Codex for downloads, categorization, reconciliation, and reporting
- do not allow autonomous payment execution

### Accounting Data Pipeline

Recommended flow:

1. download bank and card statements from `Finance`
2. save exports into fixed folders
3. run local processing scripts against those files
4. generate bookkeeping or tax workbooks in the workspace
5. keep credentials out of the data-processing layer

## Implementation Plan

### Phase 1: Secure Foundation

1. Enable `FileVault` if not already enabled.
2. Configure the required items in `macOS Keychain`.
3. Move all banking, email, accounting, and recovery secrets into Keychain or other approved secret stores.
4. Remove any plaintext credential artifacts from local files, notes, and shell history.

Exit criteria:

- all sensitive credentials are in the vault
- no passwords remain in the repo or ad hoc files

### Phase 2: Browser Isolation

1. Create browser profiles: `Finance`, `Work Admin`, `General`.
2. Sign in only the necessary accounts within each profile.
3. Remove unnecessary extensions from `Finance` and `Work Admin`.
4. Enable MFA and login alerts on key accounts.

Exit criteria:

- sensitive sites are isolated by profile
- finance activity is separated from general browsing

### Phase 3: Assistant Operating Rules

1. Define rules for what Codex may do without confirmation.
2. Define high-risk actions that always require confirmation.
3. Standardize download locations for statements, exports, and reports.
4. Decide whether Codex may send emails or only draft them.

Exit criteria:

- clear human approval boundaries exist
- download and document locations are predictable

### Phase 4: Automation Readiness

1. Test browser automation against email, calendar, and one low-risk financial workflow.
2. Validate that Codex can operate on authenticated sessions without needing stored raw passwords.
3. Add account-by-account notes for any site that requires unusual login flows or MFA prompts.

Exit criteria:

- at least one workflow each for email, calendar, and accounting works end-to-end
- no credential material is stored in the workspace

### Phase 5: Hardening and Maintenance

1. Review active sessions monthly.
2. Rotate high-risk passwords periodically and after any suspected exposure.
3. Revoke old devices and stale app sessions.
4. Audit the password manager for missing MFA and duplicated passwords.

Exit criteria:

- sessions and credentials are maintained as an ongoing system, not a one-time setup

## Immediate Next Actions

Recommended order:

1. Decide whether `macOS Keychain` alone is sufficient, or whether you also need a synced password manager.
2. Create browser profiles and name them exactly.
3. Move all root credentials into the vault.
4. Define a fixed download directory layout.
5. Test one email workflow, one calendar workflow, and one bank statement download workflow.

## Default Policy for Codex

Codex may:

- read and summarize email
- draft replies
- review calendar availability
- download statements and exports
- organize accounting files
- process exported data into reports

Codex may not, without explicit confirmation:

- send email
- move money
- change credentials or security settings
- submit filings
- delete records

## Open Decisions

You still need to choose:

- whether `macOS Keychain` alone is sufficient, or whether you also need a synced password manager
- browser: `Chrome` vs `Edge`
- whether email sending is allowed or draft-only
- whether banking access is read-only only, or if transaction-capable access will ever be used

## Recommendation

Best balanced setup for your use case:

- `macOS Keychain` for machine-local credential retrieval
- `Chrome` with `Finance`, `Work Admin`, and `General` profiles
- Codex operates only on authenticated browser sessions
- strict confirmation gates for payments, submissions, sends, and security changes
- fixed local folder structure for exports and accounting artifacts

This setup gives you the lowest operational friction without making Codex the primary holder of your credentials.
