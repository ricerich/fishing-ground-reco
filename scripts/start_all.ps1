# 어장 추천 서비스 — 네 프로세스를 각각 새 창으로 띄운다 (Windows PowerShell)
# 먼저 한 번: README 의 '처음 설치' 순서대로 (.env · init_db.py · bootstrap_demo · npm install)
# 실행: 저장소 맨 위에서  powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\ai'; .\.venv\Scripts\uvicorn api.main:app --host 127.0.0.1 --port 8000" -WindowStyle Normal
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\ai'; .\.venv\Scripts\python -m reco.worker" -WindowStyle Normal
# 실습 기본: demo + mockoauth(모의 카카오 · 네이버). 실제 키로: $env:PROFILES='demo'
$profiles = if ($env:PROFILES) { $env:PROFILES } else { 'demo,mockoauth' }
if (Get-Command mailpit -ErrorAction SilentlyContinue) { Start-Process mailpit -ArgumentList '--smtp','127.0.0.1:1025','--listen','127.0.0.1:8025' -WindowStyle Minimized }
if ($profiles -like '*mockoauth*') { Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root'; python scripts\mock_oauth.py" -WindowStyle Minimized }
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\api'; .\gradlew.bat bootRun --args='--spring.profiles.active=$profiles'" -WindowStyle Normal
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\web'; npm run dev" -WindowStyle Normal

Write-Host "AI 8000 · 작업 프로세스 · Spring 8080 · 화면 3000 을 새 창으로 띄웠습니다."
Write-Host "30초쯤 뒤 http://localhost:3000/status 에서 네 부분이 모두 '정상'인지 확인하세요."
