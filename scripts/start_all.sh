#!/usr/bin/env bash
# 네 프로세스를 한 번에 띄운다 (리눅스 · 맥). Windows 는 start_all.ps1
# 먼저 한 번: ai/.venv 만들기 · npm install · .env 채우기 · python ai/scripts/init_db.py · python -m reco.jobs run bootstrap_demo
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/scripts/logs"; mkdir -p "$LOG"
cd "$ROOT/ai"
nohup .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 > "$LOG/ai.log" 2>&1 &
nohup .venv/bin/python -m reco.worker > "$LOG/worker.log" 2>&1 &
cd "$ROOT/api"
nohup ./gradlew bootRun --args='--spring.profiles.active=demo' > "$LOG/api.log" 2>&1 &
cd "$ROOT/web"
nohup npm run dev > "$LOG/web.log" 2>&1 &
echo "AI 8000 · 작업 프로세스 · Spring 8080 · 화면 3000 을 띄웠습니다. 로그: scripts/logs/"
echo "30초쯤 뒤 http://localhost:3000/status 에서 네 부분이 모두 '정상'인지 확인하세요."
