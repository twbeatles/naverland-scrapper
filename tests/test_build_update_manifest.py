from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.build_update_manifest import build_manifest
from src.utils.update_manifest import verify_release_manifest
from cryptography.hazmat.primitives import serialization
import base64


def test_build_manifest_contains_verifiable_artifact_metadata(tmp_path):
    artifact = tmp_path / "app.exe"; artifact.write_bytes(b"release")
    key = Ed25519PrivateKey.generate()
    document = build_manifest(version="15.1", artifact=artifact, artifact_url="https://example.com/app.exe", private_key=key, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    result = verify_release_manifest(document, public_key_b64=public, current_version="15.0")
    assert result.artifact_size == len(b"release")
