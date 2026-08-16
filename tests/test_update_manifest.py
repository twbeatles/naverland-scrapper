import base64
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.utils.update_manifest import NoUpdateAvailableError, canonical_manifest_payload, verify_release_manifest


def _document(version="15.1"):
    private = Ed25519PrivateKey.generate()
    payload = {"version": version, "artifact_url": "https://github.com/twbeatles/naverland-scrapper/releases/download/v15.1/app.exe", "sha256": "0" * 64, "size": 1, "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    public = base64.b64encode(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    return {"payload": payload, "signature": base64.b64encode(private.sign(canonical_manifest_payload(payload))).decode()}, public


def test_signed_manifest_is_accepted():
    document, public = _document()
    assert verify_release_manifest(document, public_key_b64=public, current_version="15.0").version == "15.1"


def test_non_newer_signed_manifest_is_rejected():
    document, public = _document("15.0")
    try: verify_release_manifest(document, public_key_b64=public, current_version="15.0")
    except NoUpdateAvailableError: pass
    else: raise AssertionError("expected NoUpdateAvailableError")
