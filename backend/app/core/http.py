"""Shared HTTP session with a fixed-up TLS trust store.

Why: www.spaceappschallenge.org (and possibly some other NASA hosts) send an
intermediate cert ("SSL.com TLS Issuing RSA CA R1") cross-signed by the legacy
Comodo "AAA Certificate Services" root, which Fedora/Mozilla no longer trust.
Browsers fetch the modern intermediate automatically; Python does not.

Fix: trust the system CAs + the modern intermediate (signed by the trusted
"SSL.com TLS RSA Root CA 2022", stored in certs/), and enable PARTIAL_CHAIN so
OpenSSL can stop at that intermediate (same default behaviour as curl).
Verification (signatures, hostname, expiry) stays fully ON.
"""
import ssl
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

ROOT_DIR = Path(__file__).resolve().parents[3]
EXTRA_CERTS_DIR = ROOT_DIR / "certs"


def build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()  # system CA store, verification on
    for pem in sorted(EXTRA_CERTS_DIR.glob("*.pem")):
        ctx.load_verify_locations(cafile=str(pem))
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return ctx


class _SSLContextAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(*args, **kwargs)


def get_session() -> requests.Session:
    """Use this instead of bare requests.get() for any external fetch."""
    session = requests.Session()
    session.mount("https://", _SSLContextAdapter(build_ssl_context()))
    session.headers["User-Agent"] = "FlameInFreefall/0.1 (NASA Space Apps 2026)"
    return session
