# Deployment Guide

## Target Environment

- macOS host
- Python 3.11 or newer
- access to `/usr/bin/security`
- Playwright CLI available either through the bundled Codex wrapper or `playwright-cli` on `PATH`

## 1. Clone and Install

```bash
git clone <your-repo-url> assistant_ops
cd assistant_ops
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .[dev]
```

## 2. Pick a Workspace

The workspace holds local runtime state and should not be your source checkout if you want strict separation.

Example:

```bash
export WORKSPACE="$HOME/Library/Application Support/assistant-ops"
assistant-ops-init --workspace "$WORKSPACE"
```

## 3. Configure Keychain

Store secrets:

```bash
security add-generic-password -U -s assistant-ops.cibc -a card-number -w 'YOUR_CARD_NUMBER'
security add-generic-password -U -s assistant-ops.cibc -a password -w 'YOUR_PASSWORD'
```

Store the non-secret mapping:

```bash
assistant-ops-configure-keychain \
  --workspace "$WORKSPACE" \
  --cibc-card-number-service assistant-ops.cibc \
  --cibc-card-number-account card-number \
  --cibc-password-service assistant-ops.cibc \
  --cibc-password-account password
```

## 4. Configure Runtime Overrides

Only set these if your Mac differs from the defaults:

```bash
export ASSISTANT_OPS_PWCLI_PATH="/path/to/playwright_cli.sh"
export ASSISTANT_OPS_SECURITY_PATH="/usr/bin/security"
export ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION="cibc-banking"
```

## 5. Start the Service

```bash
assistant-ops-mcp --workspace "$WORKSPACE" --transport stdio
```

For remote clients that speak HTTP transports:

```bash
assistant-ops-mcp --workspace "$WORKSPACE" --transport sse --actor deployment-host
```

## 6. Publish Safety Checklist

Before pushing to GitHub:

- verify `.playwright-cli/` is not tracked
- verify `data/` is not tracked
- verify `output/` is not tracked
- verify `config/integrations.json` is not tracked
- verify no live PDFs, snapshots, audit logs, or account numbers are present in committed docs

## 7. Recommended Host Hardening

- enable FileVault
- use a non-admin daily user when possible
- keep the assistant workspace on an encrypted user account
- require Touch ID or password to unlock the Mac
- keep browser automation limited to dedicated profiles
