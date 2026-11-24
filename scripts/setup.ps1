<#
  어장 추천 서비스 — 설치 (처음 한 번, 다시 돌려도 안전)

  git clone https://github.com/ricerich/fishing-ground-reco.git
  cd fishing-ground-reco
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

  차례
    1. 필수 프로그램 확인  Git · Python 3.12+ · Java 21+ · Node.js 20.9+ · MariaDB 10.11+ (없으면 winget 명령을 알려 주고 멈춤)
    2. .env 준비           없으면 .env.example 을 복사
    3. AI 서버(+RAG)        ai\.venv 가상환경 → 파이썬 패키지
    4. 데이터베이스         MariaDB root 비밀번호를 물어봄 → DB · 계정 · 권한 · 표 (scripts\setup_db.ps1)
    5. 시연 자료            위판 · 관측 적재 → 첫 모델 reco_v1 → 7/1~오늘 추천 → 채점 (약 15초)
    6. 화면(Next.js)        npm install
    7. Spring Boot          Gradle 이 라이브러리를 받고 한 번 컴파일 (첫 구동을 빠르게)
    8. Mailpit              개발용 메일함을 tools\mailpit 에 받음
    9. Ollama 모델          Ollama 가 있으면 qwen3:1.7b 를 받음 (없으면 건너뜀 — RAG 는 근거 문장 모음으로 동작)

  선택
    -SkipDb        4 · 5 건너뛰기 (DB 를 이미 만들었을 때. 5 는 시연 상태를 처음으로 되돌린다)
    -SkipMailpit   8 건너뛰기
    -SkipOllama    9 건너뛰기
    -Only 3,6      지정한 단계만
#>
param([switch]$SkipDb, [switch]$SkipMailpit, [switch]$SkipOllama, [int[]]$Only)

$ErrorActionPreference = 'Continue'          # 외부 프로그램의 경고(stderr)로 멈추지 않게 — 종료 코드로 판단한다
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$started = Get-Date

function Step($n, $title) {
    if ($Only -and ($Only -notcontains $n)) { return $false }
    Write-Host ""
    Write-Host ("[{0}/9] {1}" -f $n, $title) -ForegroundColor Cyan
    return $true
}
function Ok($msg)   { Write-Host "  OK   $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  주의 $msg" -ForegroundColor Yellow }
function Fail($msg) {
    Write-Host "  실패 $msg" -ForegroundColor Red
    Write-Host ""
    Write-Host "고친 뒤 같은 명령으로 다시 실행하세요. 끝난 단계는 빠르게 지나갑니다. (특정 단계만: -Only 3,6)"
    exit 1
}
function Run($what, [scriptblock]$cmd) {      # 외부 명령 실행 → 종료 코드가 0 이 아니면 멈춤
    & $cmd
    if ($LASTEXITCODE -ne 0) { Fail "$what (종료 코드 $LASTEXITCODE)" }
}
function VersionOf([string]$text) {
    $m = [regex]::Match($text, '(\d+)\.(\d+)(?:\.(\d+))?')
    if ($m.Success) { return [version]("{0}.{1}.{2}" -f $m.Groups[1].Value, $m.Groups[2].Value, ($(if ($m.Groups[3].Success) { $m.Groups[3].Value } else { 0 }))) }
    return $null
}
function Native([string]$line) {               # stderr 까지 한 줄 문자열로 (java -version 은 stderr 로 찍는다)
    $out = cmd /c "$line 2>&1"
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($out | Out-String)
}

# ── 1. 필수 프로그램 ─────────────────────────────────────────
$python = $null
if (Step 1 '필수 프로그램 확인') {
    $missing = @()

    if (Get-Command git -ErrorAction SilentlyContinue) { Ok ("Git " + (VersionOf (Native 'git --version'))) }
    else { $missing += @{ name = 'Git'; winget = 'winget install --id Git.Git -e' } }

    foreach ($cand in @('py -3.13', 'py -3.12', 'python')) {
        $v = VersionOf (Native "$cand --version")
        if ($v -and $v -ge [version]'3.12.0') { $python = $cand; Ok "Python $v ($cand)"; break }
    }
    if (-not $python) { $missing += @{ name = 'Python 3.12 이상'; winget = 'winget install --id Python.Python.3.12 -e' } }

    $jv = VersionOf (Native 'java -version')
    if ($jv -and $jv.Major -ge 21) { Ok "Java $jv" }
    else { $missing += @{ name = "Java 21 이상$(if ($jv) { " (지금 $jv)" })"; winget = 'winget install --id EclipseAdoptium.Temurin.21.JDK -e' } }

    $nv = VersionOf (Native 'node --version')
    if ($nv -and $nv -ge [version]'20.9.0') { Ok "Node.js $nv" }
    else { $missing += @{ name = "Node.js 20.9 이상$(if ($nv) { " (지금 $nv)" })"; winget = 'winget install --id OpenJS.NodeJS.LTS -e' } }

    $dbOk = $false
    try { $tcp = New-Object Net.Sockets.TcpClient; $tcp.Connect('127.0.0.1', 3306); $tcp.Close(); $dbOk = $true } catch { }
    if ($dbOk) { Ok 'MariaDB (127.0.0.1:3306 응답)' }
    else {
        $svc = Get-Service -Name 'MariaDB*', 'MySQL*' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($svc) { $missing += @{ name = "MariaDB 서비스 '$($svc.Name)' 가 꺼져 있음"; winget = "관리자 PowerShell 에서: Start-Service $($svc.Name)" } }
        else { $missing += @{ name = 'MariaDB 10.11 이상 (설치할 때 root 비밀번호를 정한다)'; winget = 'winget install --id MariaDB.Server -e' } }
    }

    if ($missing.Count) {
        Write-Host ""
        Write-Host "  없는 프로그램이 있습니다. 설치한 뒤 PowerShell 창을 새로 열고 다시 실행하세요." -ForegroundColor Yellow
        foreach ($m in $missing) { Write-Host ("    - {0,-34} {1}" -f $m.name, $m.winget) }
        Fail '필수 프로그램 부족'
    }
}
if (-not $python) { foreach ($cand in @('py -3.13', 'py -3.12', 'python')) { $v = VersionOf (Native "$cand --version"); if ($v -and $v -ge [version]'3.12.0') { $python = $cand; break } } }

# ── 2. .env ───────────────────────────────────────────────
if (Step 2 '.env 준비') {
    if (Test-Path .env) { Ok '.env 있음 (그대로 둠)' }
    else { Copy-Item .env.example .env; Ok '.env.example → .env 복사 (계정 비밀번호 · 내부 토큰은 4단계에서 자동으로 채움)' }
    $envText = Get-Content .env -Raw -Encoding UTF8
    if ($envText -match '(?m)^ADMIN_EMAILS=\s*$') { Warn '관리자로 쓸 이메일을 .env 의 ADMIN_EMAILS= 에 적어 두세요 (시연은 로그인 화면의 시연 관리자로 충분)' }
}

# ── 3. AI 서버(+RAG) 파이썬 환경 ───────────────────────────
$venvPy = Join-Path $root 'ai\.venv\Scripts\python.exe'
if (Step 3 'AI 서버(+RAG) — 가상환경 · 파이썬 패키지 (처음엔 몇 분)') {
    if (-not (Test-Path $venvPy)) {
        if (-not $python) { Fail 'Python 3.12 이상을 찾지 못함 — 1단계부터' }
        Run '가상환경 만들기' { cmd /c "$python -m venv ai\.venv" }
        Ok 'ai\.venv 만듦'
    } else { Ok 'ai\.venv 있음' }
    Run 'pip 올리기' { & $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check }
    Run '패키지 설치 (ai\requirements.txt)' { & $venvPy -m pip install -r ai\requirements.txt --quiet --disable-pip-version-check }
    Ok '파이썬 패키지 설치 (FastAPI · scikit-learn · Kiwi · BM25 …)'
}

# ── 4 · 5. DB · 시연 자료 ──────────────────────────────────
if (-not $SkipDb) {
    if (Step 4 '데이터베이스 · 계정 (MariaDB root 비밀번호를 물어봄 — 저장하지 않음)') {
        & (Join-Path $root 'scripts\setup_db.ps1')
        if ($LASTEXITCODE -ne 0) { Fail 'DB 준비 — 위 메시지 확인 (비밀번호 · MariaDB 켜짐 여부)' }
    }
    if (Step 5 '시연 자료 · 첫 모델 · 추천 · 채점 (약 15초)') {
        Push-Location ai
        Run '시연 자료 준비' { & $venvPy -m reco.jobs run bootstrap_demo }
        Pop-Location
        Ok '시연 상태 준비 (오늘 = 2026-10-15, 챔피언 reco_v1)'
    }
} elseif (-not $Only) { Write-Host ""; Write-Host '[4 · 5] 건너뜀 (-SkipDb)' -ForegroundColor DarkGray }

# ── 6. 화면 ────────────────────────────────────────────────
if (Step 6 '화면(Next.js) — npm install') {
    Push-Location web
    if (Test-Path package-lock.json) { Run 'npm ci' { cmd /c "npm ci --no-audit --no-fund" } }
    else { Run 'npm install' { cmd /c "npm install --no-audit --no-fund" } }
    Pop-Location
    Ok 'web\node_modules 준비'
}

# ── 7. Spring ──────────────────────────────────────────────
if (Step 7 'Spring Boot — Gradle 라이브러리 받기 · 컴파일 (처음엔 몇 분)') {
    Push-Location api
    Run 'Gradle 컴파일' { cmd /c "gradlew.bat classes --console=plain -q" }
    Pop-Location
    Ok 'api 컴파일 (구동은 start.ps1 의 gradlew bootRun)'
}

# ── 8. Mailpit ─────────────────────────────────────────────
if (-not $SkipMailpit -and (Step 8 'Mailpit — 개발용 메일함 (가입 · 재설정 메일 확인)')) {
    $mp = Join-Path $root 'tools\mailpit\mailpit.exe'
    if (Test-Path $mp) { Ok 'tools\mailpit\mailpit.exe 있음' }
    elseif (Get-Command mailpit -ErrorAction SilentlyContinue) { Ok 'mailpit 이 PATH 에 있음' }
    else {
        $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
        $url = "https://github.com/axllent/mailpit/releases/latest/download/mailpit-windows-$arch.zip"
        $zip = Join-Path $env:TEMP 'mailpit.zip'
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
            New-Item -ItemType Directory -Force (Split-Path $mp) | Out-Null
            Expand-Archive -Path $zip -DestinationPath (Split-Path $mp) -Force
            Remove-Item $zip -ErrorAction SilentlyContinue
            Ok "Mailpit 받음 → tools\mailpit ($arch)"
        } catch { Warn "Mailpit 을 받지 못함 ($($_.Exception.Message)) — 메일 확인 없이도 나머지는 동작. 수동: $url" }
    }
} elseif ($SkipMailpit -and -not $Only) { Write-Host ""; Write-Host '[8] 건너뜀 (-SkipMailpit)' -ForegroundColor DarkGray }

# ── 9. Ollama 모델 ─────────────────────────────────────────
if (-not $SkipOllama -and (Step 9 'Ollama 모델 (RAG 설명 · 물어보기)')) {
    $model = 'qwen3:1.7b'
    $m = Select-String -Path .env -Pattern '^OLLAMA_MODEL=(.+)$' -ErrorAction SilentlyContinue
    if ($m -and $m.Matches[0].Groups[1].Value.Trim()) { $model = $m.Matches[0].Groups[1].Value.Trim() }
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        $list = Native 'ollama list'
        if ($null -eq $list) { Warn 'Ollama 가 응답하지 않음 — 작업 표시줄의 Ollama 를 켠 뒤 다시: -Only 9' }
        elseif ($list -match [regex]::Escape($model)) { Ok "$model 있음" }
        else {
            Write-Host "  $model 받는 중 (약 1.4GB)…"
            cmd /c "ollama pull $model"
            if ($LASTEXITCODE -eq 0) { Ok "$model 받음" } else { Warn "$model 을 받지 못함 — 나중에: ollama pull $model" }
        }
    } else {
        Warn 'Ollama 가 없음 — RAG 는 근거 문장 모음으로 답합니다. LLM 으로 쓰려면: winget install --id Ollama.Ollama -e 후 -Only 9'
    }
} elseif ($SkipOllama -and -not $Only) { Write-Host ""; Write-Host '[9] 건너뜀 (-SkipOllama)' -ForegroundColor DarkGray }

$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
Write-Host ""
Write-Host "설치 끝 ($mins 분). 구동:  powershell -ExecutionPolicy Bypass -File scripts\start.ps1" -ForegroundColor Green
