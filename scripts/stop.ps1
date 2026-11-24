<#
  어장 추천 서비스 — 끄기. start.ps1 이 띄운 창(과 그 안의 서버)을 모두 닫는다.
  powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
#>
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root 'scripts\.pids'
$n = 0

# 1) start.ps1 이 적어 둔 창 PID — 창과 그 아래 프로세스(uvicorn · java · node …)를 통째로
if (Test-Path $pidFile) {
    foreach ($id in Get-Content $pidFile) {
        if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) { cmd /c "taskkill /T /F /PID $id >nul 2>&1"; $n++ }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

# 2) 그래도 남은 것 — 포트를 붙잡은 프로세스, 작업 프로세스(포트 없음), Gradle 데몬은 그대로 둔다(다음 구동이 빨라짐)
foreach ($port in 3000, 8000, 8080, 8025, 1025, 9100) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { if ($_.OwningProcess -gt 4) { cmd /c "taskkill /T /F /PID $($_.OwningProcess) >nul 2>&1"; $n++ } }
}
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*reco.worker*' -or $_.CommandLine -like '*mock_oauth.py*' } |
    ForEach-Object { cmd /c "taskkill /T /F /PID $($_.ProcessId) >nul 2>&1"; $n++ }

Write-Host ("어장 추천 서비스를 껐습니다 (닫은 프로세스 {0}개)." -f $n) -ForegroundColor Green
