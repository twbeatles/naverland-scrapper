from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.update_manifest import canonical_manifest_payload, version_tuple
from src.utils.version import UPDATE_PUBLIC_KEY_B64


def build_manifest(*, version: str, artifact: Path, artifact_url: str, private_key: Ed25519PrivateKey, expires_at: datetime) -> dict[str, object]:
    version_tuple(version)
    if artifact.suffix.lower() != ".exe" or not artifact.is_file() or not artifact_url.startswith("https://"):
        raise ValueError("A local .exe and HTTPS artifact URL are required")
    digest = hashlib.sha256(); size = 0
    with artifact.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk); size += len(chunk)
    payload = {"version": version.removeprefix("v"), "artifact_url": artifact_url, "sha256": digest.hexdigest(), "size": size, "expires_at": expires_at.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    return {"payload": payload, "signature": base64.b64encode(private_key.sign(canonical_manifest_payload(payload))).decode("ascii")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a signed update manifest")
    parser.add_argument("--version", required=True); parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--artifact-url", required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-key-env", default="NAVERLAND_UPDATE_PRIVATE_KEY_B64")
    parser.add_argument("--expires-in-days", type=int, default=365)
    args = parser.parse_args(argv)
    raw = os.environ.get(args.private_key_env, "")
    if not raw: raise ValueError(f"Required environment variable is not set: {args.private_key_env}")
    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw, validate=True))
    derived_public = base64.b64encode(private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    if not UPDATE_PUBLIC_KEY_B64 or derived_public != UPDATE_PUBLIC_KEY_B64:
        raise ValueError("The private signing key does not match UPDATE_PUBLIC_KEY_B64")
    document = build_manifest(version=args.version, artifact=args.artifact.resolve(), artifact_url=args.artifact_url, private_key=private_key, expires_at=datetime.now(timezone.utc) + timedelta(days=args.expires_in_days))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
