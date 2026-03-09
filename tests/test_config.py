from pathlib import Path

from assistant_ops.config import Settings


def test_settings_use_environment_overrides(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASSISTANT_OPS_PWCLI_PATH", "/tmp/custom-playwright-cli")
    monkeypatch.setenv("ASSISTANT_OPS_SECURITY_PATH", "/tmp/custom-security")
    monkeypatch.setenv("ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION", "portable-session")

    settings = Settings.for_workspace(tmp_path)

    assert settings.pwcli_path == Path("/tmp/custom-playwright-cli")
    assert settings.security_path == Path("/tmp/custom-security")
    assert settings.cibc_playwright_session == "portable-session"


def test_settings_fall_back_to_path_lookup_when_bundled_wrapper_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ASSISTANT_OPS_PWCLI_PATH", raising=False)
    monkeypatch.delenv("ASSISTANT_OPS_SECURITY_PATH", raising=False)
    monkeypatch.delenv("ASSISTANT_OPS_CIBC_PLAYWRIGHT_SESSION", raising=False)
    original_exists = Path.exists
    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: False if str(self).endswith("playwright_cli.sh") else original_exists(self),
    )

    settings = Settings.for_workspace(tmp_path)

    assert settings.pwcli_path == Path("playwright-cli")
