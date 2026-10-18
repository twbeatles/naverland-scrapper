# Mirrors .github/workflows/ci.yml locally (Windows).
# Usage: powershell -File scripts/ci_check.ps1
#
# Run this before every push that touches src/ui or tests — GitHub CI fails the
# same pyright + pytest subset steps. UI helpers that wrap QWidget (e.g.
# prepare_page) must preserve concrete types (TypeVar) so attributes like
# CrawlerTab.table_list stay visible to pyright.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# 격리 환경(.venv-ci, scripts/setup_build_env.ps1)이 있으면 그것만 쓴다.
# 전역 Python의 PySide6-Fluent-Widgets 등이 qfluentwidgets를 덮어써 검사가 오염되는 것을 막는다.
$venvPython = Join-Path (Get-Location) ".venv-ci\Scripts\python.exe"
function Test-PythonRuntime([string]$Executable) {
  if (-not (Test-Path -LiteralPath $Executable)) { return $false }
  try { & $Executable -c "import sys" *> $null } catch { return $false }
  return $LASTEXITCODE -eq 0
}
if (Test-PythonRuntime $venvPython) {
  $py = $venvPython
  $env:PYTHONNOUSERSITE = "1"
  Write-Host "Using isolated env: $py"
} elseif (Test-PythonRuntime (Join-Path (Get-Location) ".venv\Scripts\python.exe")) {
  $py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
  $env:PYTHONNOUSERSITE = "1"
  Write-Host "Using working project env: $py (.venv-ci unavailable)"
} else {
  $py = "python"
  Write-Host "격리 환경(.venv-ci)이 없습니다. 'powershell -File scripts/setup_build_env.ps1' 로 만들면 전역 환경과 분리됩니다." -ForegroundColor Yellow
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK = "1"
$env:QT_QPA_PLATFORM = if ($env:QT_QPA_PLATFORM) { $env:QT_QPA_PLATFORM } else { "offscreen" }

Write-Host "== Syntax check =="
& $py -m compileall -q app_entry.py src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Pyright =="
npx --yes pyright --pythonpath $py
if ($LASTEXITCODE -ne 0) {
  Write-Host "Pyright failed. Fix type errors before push (CI will fail on the same step)." -ForegroundColor Red
  exit $LASTEXITCODE
}

Write-Host "== Pytest (CI subset) =="
& $py -m pytest -q `
  tests/test_parser_module.py `
  tests/test_app_entry.py `
  tests/test_main_paths.py `
  tests/test_article_api.py `
  tests/test_collection_integrity.py `
  tests/test_playwright_engine_stabilization.py `
  tests/test_response_capture_normalize.py `
  tests/test_geo_markers_cortar.py `
  tests/test_site_contract.py `
  tests/test_crawler_regressions.py `
  tests/test_crawl_lock.py `
  tests/test_paths_runtime.py `
  tests/test_live_smoke.py `
  tests/test_analysis.py `
  tests/test_database_module.py `
  tests/test_ui_wiring.py `
  tests/test_ui_runtime_smoke.py `
  tests/test_export_module.py `
  tests/test_rebind_methods.py `
  tests/test_detail_fetcher.py `
  tests/test_solid_split_facades.py `
  tests/test_browser_pool_guard.py `
  tests/test_ci_subset_sync.py `
  tests/test_gap_analysis.py `
  tests/test_managers_cache.py `
  tests/test_mojibake_scan.py `
  tests/test_preflight.py `
  tests/test_fluent_theme.py `
  tests/test_requirements_pins.py `
  tests/test_crawl_preflight.py `
  tests/test_release_workflow.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Preflight =="
& $py -m src.utils.preflight
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "CI check passed."
