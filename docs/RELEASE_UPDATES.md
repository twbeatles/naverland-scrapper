# GitHub Release updates

The app downloads only `updates/latest.json` over HTTPS, verifies its Ed25519 signature using the public key compiled into `src/utils/version.py`, then verifies the downloaded EXE's exact SHA-256 and byte size before it is installed.

One-time setup:

1. Generate a 32-byte Ed25519 private key and base64 encode it. Store it only as GitHub Actions secret `NAVERLAND_UPDATE_PRIVATE_KEY_B64`.
2. Derive its 32-byte public key, base64 encode it, and set `UPDATE_PUBLIC_KEY_B64` in `src/utils/version.py`. Never commit the private key.
3. Tag `vX.Y.Z` only after updating `APP_VERSION` to that same value.

For example, this prints both values locally; copy only the `public` value into source and put only the `private` value in the GitHub secret:

```powershell
python -c "import base64; from cryptography.hazmat.primitives import serialization; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K; k=K.generate(); print('private='+base64.b64encode(k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode()); print('public='+base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())"
```

The release workflow (`.github/workflows/release.yml`) runs on GitHub-hosted `windows-latest` with `actions/checkout@v7`, `actions/setup-python@v7` (Python 3.14, pip cache), and `softprops/action-gh-release@v3`. It builds a one-file EXE, uploads it with the signed manifest to GitHub Releases, and commits that manifest to `updates/latest.json` on `main`. The running application first shuts down active collection, then starts a copied helper. The helper waits for exit, replaces the EXE, runs `--preflight`, rolls back on failure, and restarts only a validated build.

Weekly Dependabot version-update PRs are disabled (no `.github/dependabot.yml`). Bump pip floors in `requirements.txt` and action majors in the workflow files when needed. GitHub Dependabot security alerts can still be used independently.
