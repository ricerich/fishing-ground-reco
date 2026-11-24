<#
  어장 추천 서비스 — 구동 (수업마다). 각 서버를 제목 붙은 새 창으로 띄우고, 모두 '정상'이 될 때까지 기다린 뒤 브라우저를 연다.

  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Profiles demo     # 실제 소셜 키로 (모의 소셜 서버 없이)
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -NoBrowser

  띄우는 것 (개발 모드 — 코드를 고치면 바로 반영)
    Mailpit        :8025 메일함 · :1025 SMTP          tools\mailpit\mailpit.exe (있을 때)
    모의 소셜 로그인 :9100                            -Profiles 에 mockoauth 가 있을 때
    AI 서버(+RAG)   :8000  uvicorn --reload
    작업 프로세스    수집 · 추천 계산 · 채점 · 재학습 · 관리자 요청 대기열
    Spring Boot    :8080  gradlew bootRun (프로필 demo,mockoauth)
    화면 Next.js    :3000  npm run dev
  끄기: scripts\stop.ps1
#>
param([string]$Profiles = 'demo,mockoauth', [switch]$NoBrowser, [int]$TimeoutSec = 300)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'ai\.venv\Scripts\python.exe'
$pidFile = Join-Path $root 'scripts\.pids'

if (-not (Test-Path $py)) { Write-Host '설치가 먼저입니다: scripts\setup.ps1' -ForegroundColor Red; exit 1 }
if (-not (Test-Path (Join-Path $root 'web\node_modules'))) { Write-Host 'web\node_modules 가 없습니다: scripts\setup.ps1 -Only 6' -ForegroundColor Red; exit 1 }

$busy = @(3000, 8000, 8080) | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue }
if ($busy) {
    Write-Host ("포트 {0} 를 이미 쓰는 프로그램이 있습니다. 먼저 scripts\stop.ps1 (또는 그 프로그램을 끄기)" -f ($busy -join ', ')) -ForegroundColor Red
    exit 1
}

$common = "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[Text.Encoding]::UTF8;"
$pids = @()
function Launch($title, $dir, $command, [switch]$Min) {
    $cmd = "$common `$host.UI.RawUI.WindowTitle='어장추천 · $title'; Set-Location -LiteralPath '$dir'; $command"
    $p = Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd `
        -WindowStyle $(if ($Min) { 'Minimized' } else { 'Normal' }) -PassThru
    $script:pids += $p.Id
    Write-Host ("  띄움  {0,-16} (창 PID {1})" -f $title, $p.Id)
}

Write-Host "어장 추천 서비스를 띄웁니다 (프로필 $Profiles)" -ForegroundColor Cyan

$mailpit = Join-Path $root 'tools\mailpit\mailpit.exe'
if (-not (Test-Path $mailpit)) { $c = Get-Command mailpit -ErrorAction SilentlyContinue; if ($c) { $mailpit = $c.Source } else { $mailpit = $null } }
if ($mailpit) { Launch '메일함 Mailpit' $root "& '$mailpit' --smtp 127.0.0.1:1025 --listen 127.0.0.1:8025" -Min }
else { Write-Host '  건너뜀 Mailpit (없음 — 가입 · 재설정 메일은 보낼 수 없음. scripts\setup.ps1 -Only 8)' -ForegroundColor Yellow }

if ($Profiles -like '*mockoauth*') { Launch '모의 소셜 로그인' $root "& '$py' scripts\mock_oauth.py" -Min }
Launch 'AI 서버(+RAG)' "$root\ai" "& '$py' -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir api --reload-dir reco"
Launch '작업 프로세스' "$root\ai" "& '$py' -m reco.worker"
Launch 'Spring Boot' "$root\api" ".\gradlew.bat bootRun --console=plain --args='--spring.profiles.active=$Profiles'"
Launch '화면 Next.js' "$root\web" "npm run dev"
$pids -join "`n" | Set-Content -Path $pidFile -Encoding ASCII

# 모두 뜰 때까지 기다리기 (Spring 은 처음 bootRun 때 1~2분)
$checks = [ordered]@{
    'AI 서버(+RAG)' = 'http://127.0.0.1:8000/health'
    'Spring Boot'  = 'http://127.0.0.1:8080/api/health'
    '화면 Next.js'  = 'http://localhost:3000/api/meta'
}
$up = @{}
$t0 = Get-Date
Write-Host ""
Write-Host "모두 준비될 때까지 기다립니다 (최대 $TimeoutSec 초)…"
while ($up.Count -lt $checks.Count -and ((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
    foreach ($k in $checks.Keys) {
        if ($up.ContainsKey($k)) { continue }
        try {
            $r = Invoke-WebRequest -Uri $checks[$k] -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $up[$k] = [int]((Get-Date) - $t0).TotalSeconds; Write-Host ("  정상  {0,-14} {1}초" -f $k, $up[$k]) -ForegroundColor Green }
        } catch { }
    }
    Start-Sleep -Seconds 2
}
foreach ($k in $checks.Keys) { if (-not $up.ContainsKey($k)) { Write-Host ("  아직  {0,-14} — 그 창의 마지막 줄을 확인하세요" -f $k) -ForegroundColor Yellow } }

Write-Host ""
Write-Host '주소' -ForegroundColor Cyan
Write-Host '  화면          http://localhost:3000        (시연 사용자 · 시연 관리자는 로그인 화면에서)'
Write-Host '  시스템 상태    http://localhost:3000/status'
Write-Host '  AI 서버 문서   http://127.0.0.1:8000/docs'
if ($mailpit) { Write-Host '  메일함        http://localhost:8025' }
Write-Host '  끄기          scripts\stop.ps1'
if (-not $NoBrowser -and $up.Contains('화면 Next.js')) { Start-Process 'http://localhost:3000/status' }
if ($up.Count -lt $checks.Count) { exit 1 }
