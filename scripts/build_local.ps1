# 로컬 PyInstaller 빌드 (격리 가상환경 사용).
# Usage:
#   powershell -File scripts/build_local.ps1             # onedir  → dist/naverland/
#   powershell -File scripts/build_local.ps1 -OneFile    # onefile → dist/naverland_onefile.exe
#   powershell -File scripts/build_local.ps1 -OneFile -Slim   # Chromium 번들 제외
#
# 전역 Python 대신 .venv-ci 만 사용하므로 전역에 충돌 패키지가 있어도 빌드가 오염되지 않는다.
param(
  [switch]$OneFile,
  [switch]$Slim,
  [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$venvPython = Join-Path (Get-Location) ".venv-ci\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "격리 환경이 없어 먼저 만듭니다." -ForegroundColor Yellow
  powershell -File scripts/setup_build_env.ps1
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:PYTHONNOUSERSITE = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK = "1"
$env:NAVERLAND_SKIP_PLAYWRIGHT_TESTS = "1"
$env:QT_QPA_PLATFORM = "offscreen"

Write-Host "== Qt binding check =="
& $venvPython -I -c "import sys; sys.path.insert(0, '.'); from src.utils.preflight import find_qfluentwidgets_binding_mismatch as f; e = f(); print(e or 'OK'); sys.exit(1 if e else 0)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
  Write-Host "== Tests =="
  & $venvPython -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:NAVERLAND_ONEFILE = if ($OneFile) { "1" } else { "0" }
$env:NAVERLAND_BUNDLE_CHROMIUM = if ($Slim) { "0" } else { "1" }

Write-Host "== PyInstaller =="
& $venvPython -m PyInstaller --clean --noconfirm naverland-scrapper.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Frozen preflight =="
$exe = Get-ChildItem dist -Recurse -Filter "*.exe" | Where-Object { $_.Name -like "naverland*" } | Select-Object -First 1
if ($null -eq $exe) { throw "PyInstaller did not create an EXE" }
& $exe.FullName --preflight
if ($LASTEXITCODE -ne 0) { throw "Frozen preflight failed" }
Write-Host "Build OK: $($exe.FullName)"
