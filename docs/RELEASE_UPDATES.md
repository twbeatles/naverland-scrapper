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

The release workflow (`.github/workflows/release.yml`) runs on GitHub-hosted `windows-latest` with `actions/checkout@v7`, `actions/setup-python@v7` (Python 3.15, pip cache), and `softprops/action-gh-release@v3`. It builds a one-file EXE, uploads it with the signed manifest and release notes to GitHub Releases, and commits that manifest to `updates/latest.json` on `main`. The running application first shuts down active collection, then starts a copied helper with a cleaned bootloader environment. The helper waits for exit, swaps the EXE with two renames (installed -> backup, staged -> installed; stale backups are overwritten and an interrupted swap is recovered on the next run), runs `--preflight` in a cleaned environment, rolls back via rename (failed build aside, backup home) on failure, and restarts only a validated build with a cleaned environment.

Local builds should use the isolated `.venv-ci` (`scripts/setup_build_env.ps1`, then `scripts/build_local.ps1 -OneFile`) so packages in the global or user site (for example `PySide6-Fluent-Widgets`, which overwrites `qfluentwidgets`) cannot leak into the EXE. The release workflow runs on a clean runner with `PYTHONNOUSERSITE=1` and fails early if `qfluentwidgets` is not the PyQt6 variant.

Weekly Dependabot version-update PRs are disabled (no `.github/dependabot.yml`). Bump pip floors in `requirements.txt` and action majors in the workflow files when needed. GitHub Dependabot security alerts can still be used independently.
