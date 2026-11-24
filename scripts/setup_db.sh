#!/usr/bin/env bash
# MariaDB root 비밀번호를 물어보고 → 데이터베이스 reco · app, 계정 reco_ai · reco_api, 권한, reco 표 · 뷰
#   scripts/setup_db.sh                     (먼저: cd ai && python -m venv .venv && .venv/bin/pip install -r requirements.txt)
#   scripts/setup_db.sh --socket /run/mysqld/mysqld.sock     리눅스에서 root 가 소켓 인증일 때 (sudo 로 실행)
#   scripts/setup_db.sh --help              다른 선택지
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/ai/.venv/bin/python"
[ -x "$PY" ] || { echo "ai/.venv 가 없습니다 — README '처음 설치' 3번의 venv · pip 를 먼저"; exit 1; }
exec "$PY" "$ROOT/ai/scripts/setup_db.py" "$@"
