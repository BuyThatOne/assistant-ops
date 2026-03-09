# Google Setup Guide

## Goal

Set up Gmail and Google Calendar access for `assistant-ops` on a Mac host using Google APIs and macOS Keychain.

## 1. Create a Google Cloud Project

1. Open Google Cloud Console.
2. Create a new project or select an existing one for `assistant-ops`.
3. Enable:
   - Gmail API
   - Google Calendar API

## 2. Configure the OAuth Consent Screen

1. Open the OAuth consent screen configuration.
2. Choose the appropriate user type.
3. Set the application name and support email.
4. Add yourself as a test user if the app is in testing mode.
5. Add the Gmail and Calendar scopes required by your rollout.

## 3. Create a Desktop OAuth Client

Create an OAuth client of type:

- `Desktop app`

Record:

- client ID
- client secret

Do not commit either value into the repository.

## 4. Store the Google Client Secret in Keychain

```bash
security add-generic-password -U -s assistant-ops.google -a client-secret -w 'YOUR_GOOGLE_CLIENT_SECRET'
```

## 5. Write the Local Non-Secret Google Config

```bash
export WORKSPACE="$PWD"
assistant-ops-configure-google \
  --workspace "$WORKSPACE" \
  --google-client-id 'your-client-id.apps.googleusercontent.com' \
  --google-oauth-port 8765 \
  --google-client-secret-service assistant-ops.google \
  --google-client-secret-account client-secret \
  --google-refresh-token-service assistant-ops.google \
  --google-refresh-token-account refresh-token
```

Optional fallback:

```bash
export ASSISTANT_OPS_GOOGLE_CLIENT_ID='your-client-id.apps.googleusercontent.com'
export ASSISTANT_OPS_GOOGLE_OAUTH_PORT='8765'
```

## 6. Run the Bootstrap Flow

```bash
assistant-ops-google-auth --workspace "$WORKSPACE"
```

This will:

- open the Google consent screen
- listen for the localhost OAuth callback
- exchange the authorization code for tokens
- store the refresh token in macOS Keychain
- write the non-secret token location into `config/integrations.json`

If you hit an SSL certificate verification failure during token exchange, update to the current code in this repo and rerun the bootstrap. The runtime now uses an explicit CA bundle for Google HTTPS calls instead of relying entirely on the local Python certificate store.

## 7. Verify

Once the bootstrap completes, the normal email/calendar MCP tools should use Google APIs automatically.

Suggested checks:

- `list_email_threads`
- `draft_email_reply`
- `send_email`
- `list_calendar_events`
- `create_calendar_event`

Live validation status in this repo:

- `list_email_threads`: validated against a real Gmail account
- `draft_email_reply`: validated against a real Gmail thread
- `list_calendar_events`: validated against a real Google Calendar
- `create_calendar_event`: validated against a real Google Calendar
- `send_email`: code path is implemented and unit-tested, but not exercised live by default because the current Gmail flow sends replies into existing threads

## Notes

- access tokens are kept in memory only
- refresh tokens are stored in macOS Keychain
- if scopes or client credentials change, rerun the bootstrap flow
