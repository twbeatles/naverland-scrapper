# 빌드·검증 전용 격리 가상환경(.venv-ci)을 만든다.
# 전역/사용자 Python에 PySide6-Fluent-Widgets 같은 충돌 패키지가 있어도
# 빌드와 테스트가 영향을 받지 않게 하는 것이 목적이다 (전역 환경은 건드리지 않는다).
#
# Usage:
#   powershell -File scripts/setup_build_env.ps1            # 없으면 생성, 있으면 요구 패키지만 동기화
#   powershell -File scripts/setup_build_env.ps1 -Recreate  # 처음부터 다시 만들기
#   powershell -File scripts/setup_build_env.ps1 -Python 3.14
param(
  [switch]$Recreate,
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$venv = Join-Path (Get-Location) ".venv-ci"
$venvPython = Join-Path $venv "Scripts\python.exe"

if ($Recreate -and (Test-Path $venv)) {
  Write-Host "== Removing $venv =="
  Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $venvPython)) {
  Write-Host "== Creating isolated venv (.venv-ci) =="
  if ($Python) {
    py "-$Python" -m venv $venv
  } else {
    python -m venv $venv
  }
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# 사용자 site-packages(%APPDATA%\Python\...)가 섞여 들어오지 않게 한다.
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONUTF8 = "1"

Write-Host "== Installing requirements =="
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPython -m pip install -r requirements.txt pytest pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Verifying Qt binding =="
& $venvPython -I -c "import sys; sys.path.insert(0, '.'); from src.utils.preflight import find_qfluentwidgets_binding_mismatch as f; e = f(); print(e or 'qfluentwidgets: PyQt6 OK'); sys.exit(1 if e else 0)"
if ($LASTEXITCODE -ne 0) {
  Write-Host "qfluentwidgets 바인딩이 맞지 않습니다. -Recreate 로 다시 만들어 주세요." -ForegroundColor Red
  exit $LASTEXITCODE
}

Write-Host "Build env ready: $venvPython"
