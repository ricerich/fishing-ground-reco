#!/usr/bin/env bash
# 네 프로세스를 한 번에 띄운다 (리눅스 · 맥). Windows 는 scripts\setup.ps1 · start.ps1 · stop.ps1
# 먼저 한 번: ai/.venv 만들기 · npm install · .env 채우기 · python ai/scripts/init_db.py · python -m reco.jobs run bootstrap_demo
# 실습 기본 프로필: demo(시연 날짜 · 시연 로그인) + mockoauth(모의 카카오 · 네이버). 실제 키로 돌릴 때: PROFILES=demo scripts/start_all.sh
PROFILES="${PROFILES:-demo,mockoauth}"
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/scripts/logs"; mkdir -p "$LOG"
cd "$ROOT/ai"
nohup .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 > "$LOG/ai.log" 2>&1 &
nohup .venv/bin/python -m reco.worker > "$LOG/worker.log" 2>&1 &
if command -v mailpit >/dev/null; then nohup mailpit --smtp 127.0.0.1:1025 --listen 127.0.0.1:8025 > "$LOG/mailpit.log" 2>&1 & fi
case "$PROFILES" in *mockoauth*) nohup python3 "$ROOT/scripts/mock_oauth.py" > "$LOG/mock_oauth.log" 2>&1 & ;; esac
cd "$ROOT/api"
nohup ./gradlew bootRun --args="--spring.profiles.active=$PROFILES" > "$LOG/api.log" 2>&1 &
cd "$ROOT/web"
nohup npm run dev > "$LOG/web.log" 2>&1 &
echo "AI 8000 · 작업 프로세스 · Spring 8080($PROFILES) · 화면 3000 · 메일함 8025 · 모의 소셜 9100 을 띄웠습니다. 로그: scripts/logs/"
echo "30초쯤 뒤 http://localhost:3000/status 에서 네 부분이 모두 '정상'인지 확인하세요."
