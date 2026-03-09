from __future__ import annotations

import os
import ssl
from pathlib import Path


DEFAULT_CA_BUNDLE_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/private/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
)


def build_ssl_context() -> ssl.SSLContext:
    cafile = _resolve_ca_bundle()
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def _resolve_ca_bundle() -> str | None:
    env_path = os.getenv("SSL_CERT_FILE")
    if env_path and Path(env_path).exists():
        return env_path

    try:
        import certifi
    except ImportError:
        certifi = None

    if certifi is not None:
        certifi_path = certifi.where()
        if certifi_path and Path(certifi_path).exists():
            return certifi_path

    for candidate in DEFAULT_CA_BUNDLE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None
