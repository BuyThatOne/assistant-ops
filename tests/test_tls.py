from __future__ import annotations

import ssl

from assistant_ops import tls


def test_resolve_ca_bundle_prefers_env(monkeypatch, tmp_path) -> None:
    cafile = tmp_path / "ca.pem"
    cafile.write_text("dummy", encoding="utf-8")
    monkeypatch.setenv("SSL_CERT_FILE", str(cafile))

    assert tls._resolve_ca_bundle() == str(cafile)


def test_resolve_ca_bundle_uses_default_candidate(monkeypatch) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setattr(tls, "DEFAULT_CA_BUNDLE_CANDIDATES", ("/tmp/test-ca.pem",))

    class FakePath:
        def __init__(self, value: str) -> None:
            self.value = value

        def exists(self) -> bool:
            return self.value == "/tmp/test-ca.pem"

    monkeypatch.setattr(tls, "Path", FakePath)

    assert tls._resolve_ca_bundle() == "/tmp/test-ca.pem"


def test_build_ssl_context_returns_context(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_create_default_context(*, cafile: str | None = None) -> ssl.SSLContext:
        captured["cafile"] = cafile
        return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(tls, "_resolve_ca_bundle", lambda: "/tmp/test-ca.pem")
    monkeypatch.setattr(tls.ssl, "create_default_context", fake_create_default_context)

    context = tls.build_ssl_context()

    assert isinstance(context, ssl.SSLContext)
    assert captured["cafile"] == "/tmp/test-ca.pem"
