"""Verification for signed, GitHub-hosted application updates."""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_VERSION = re.compile(r"^\d+(?:\.\d+)*$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_MANIFEST_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20


class NoUpdateAvailableError(ValueError):
    """The valid manifest does not describe a newer version."""


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    version: str
    artifact_url: str
    artifact_sha256: str
    artifact_size: int
    expires_at: datetime


def version_tuple(value: str) -> tuple[int, ...]:
    value = str(value or "").strip().removeprefix("v")
    if not _VERSION.fullmatch(value):
        raise ValueError(f"Invalid version: {value}")
    return tuple(int(part) for part in value.split("."))


def is_newer_version(candidate: str, current: str) -> bool:
    left, right = version_tuple(candidate), version_tuple(current)
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)) > right + (0,) * (width - len(right))


def canonical_manifest_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_release_manifest(document: bytes | str | Mapping[str, Any], *, public_key_b64: str, current_version: str, now: datetime | None = None) -> ReleaseManifest:
    raw = document if isinstance(document, bytes) else (document.encode("utf-8") if isinstance(document, str) else canonical_manifest_payload(document))
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest size exceeds the allowed limit")
    try:
        parsed = json.loads(raw.decode("utf-8")) if not isinstance(document, Mapping) else dict(document)
        payload = dict(parsed["payload"])
        signature = base64.b64decode(str(parsed["signature"]), validate=True)
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
        key.verify(signature, canonical_manifest_payload(payload))
    except (KeyError, TypeError, ValueError, InvalidSignature, json.JSONDecodeError) as exc:
        raise ValueError("Manifest signature verification failed") from exc
    version = str(payload.get("version", "")).strip()
    if not is_newer_version(version, current_version):
        raise NoUpdateAvailableError("Manifest version is not newer")
    artifact_url = str(payload.get("artifact_url", "")).strip()
    if (url := urlsplit(artifact_url)).scheme != "https" or not url.hostname:
        raise ValueError("Manifest artifact_url must be HTTPS")
    sha256 = str(payload.get("sha256", "")).lower().strip()
    if not _SHA256.fullmatch(sha256):
        raise ValueError("Manifest sha256 is invalid")
    try:
        size = int(payload.get("size", 0))
        expiry = datetime.fromisoformat(str(payload.get("expires_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Manifest metadata is invalid") from exc
    if size <= 0 or size > MAX_ARTIFACT_BYTES:
        raise ValueError("Manifest artifact size is invalid")
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= (now or datetime.now(timezone.utc)):
        raise ValueError("Manifest is expired")
    return ReleaseManifest(version, artifact_url, sha256, size, expiry)


def download_release_manifest(url: str) -> bytes:
    parsed = urlsplit(str(url).strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Update manifest URL must be HTTPS")
    with urlopen(Request(url, headers={"User-Agent": "NaverlandScrapper-Updater"}), timeout=REQUEST_TIMEOUT_SECONDS) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or not final.hostname:
            raise ValueError("Manifest redirect must remain HTTPS")
        data = response.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest size exceeds the allowed limit")
    return data
