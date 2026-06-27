# Mirrors .github/workflows/ci.yml locally (Windows).
# Usage: powershell -File scripts/ci_check.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK = "1"
$env:NAVERLAND_SKIP_PLAYWRIGHT_TESTS = "1"

Write-Host "== Syntax check =="
python -m compileall -q app_entry.py src tests

Write-Host "== Pyright =="
npx --yes pyright
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Pytest (CI subset) =="
python -m pytest -q `
  tests/test_parser_module.py `
  tests/test_app_entry.py `
  tests/test_main_paths.py `
  tests/test_article_api.py `
  tests/test_paths_runtime.py `
  tests/test_live_smoke.py `
  tests/test_analysis.py `
  tests/test_database_module.py `
  tests/test_ui_wiring.py `
  tests/test_ui_runtime_smoke.py `
  tests/test_export_module.py `
  tests/test_rebind_methods.py `
  tests/test_detail_fetcher.py `
  tests/test_gap_analysis.py `
  tests/test_managers_cache.py `
  tests/test_mojibake_scan.py `
  tests/test_preflight.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Preflight =="
python -m src.utils.preflight
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "CI check passed."