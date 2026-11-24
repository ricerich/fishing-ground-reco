# MariaDB root 비밀번호를 물어보고 → 데이터베이스 reco · app, 계정 reco_ai · reco_api, 권한, reco 표 · 뷰
#   powershell -ExecutionPolicy Bypass -File scripts\setup_db.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup_db.ps1 --help
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'ai\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Host "ai\.venv 가 없습니다 — README '처음 설치' 3번의 venv · pip 를 먼저"; exit 1 }
& $py (Join-Path $root 'ai\scripts\setup_db.py') @args
exit $LASTEXITCODE
