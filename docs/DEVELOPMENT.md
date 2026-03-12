# Development Guide

## Principles

- Keep provider interfaces small and explicit.
- Keep runtime state outside source-controlled files.
- Add tests for every new settings path, parser, or browser-flow branch.
- Prefer environment-configurable paths over machine-specific defaults.
- Keep setup and bootstrap as CLI commands, but route operational actions through MCP tools.

## Install for Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .[dev]
python3 -m pytest
```

## Main Extension Points

Source modules:

- `src/assistant_ops/server.py`
  MCP tool registration and dependency wiring.
- `src/assistant_ops/services.py`
  policy-aware service orchestration.
- `src/assistant_ops/adapters.py`
  provider interfaces and implementations.
- `src/assistant_ops/cibc_session.py`
  browser automation flow logic.
- `src/assistant_ops/cibc_parser.py`
  snapshot parsers for CIBC pages.
- `src/assistant_ops/google_auth.py`
  Google OAuth bootstrap flow and Keychain persistence.
- `src/assistant_ops/google_client.py`
  Google token refresh and HTTP client primitives.
- `src/assistant_ops/tls.py`
  TLS CA-bundle selection for Google HTTPS calls on macOS.
- `src/assistant_ops/config.py`
  workspace and runtime configuration.

## Adding a New Provider

1. Define or extend a provider protocol in `adapters.py`.
2. Add a concrete implementation behind that protocol.
3. Wire it into `server.py`.
4. Add service-level behavior in `services.py`.
5. Add parser tests or service tests as needed.

## Testing Strategy

- parser changes belong in focused unit tests
- settings and config changes need dedicated regression tests
- browser-flow logic needs sequenced fake-runner tests
- Google HTTPS/TLS handling needs regression coverage because local Python certificate stores differ across Macs
- live banking validation should never be required for CI
- live Google validation should never be required for CI

Run all tests:

```bash
python3 -m pytest
```

Run focused suites:

```bash
python3 -m pytest tests/test_cibc_session.py tests/test_cibc_parser.py
```

## Local State Model

Generated local files:

- `data/`
- `output/`
- `.playwright-cli/`
- `config/integrations.json`

These are ignored on purpose. Treat them as operator-local state, not source artifacts.

## Publishing Workflow

Before opening a GitHub repo:

1. run the test suite
2. verify ignored runtime files are absent from `git status`
3. review docs for absolute paths or live account data
4. keep design docs high-level and environment-agnostic
