#!/usr/bin/env bash
# 점검 한 번에 — 단위 테스트(파이썬 · 자바 · 화면) → 통합 점검(네 부분이 떠 있어야) → 화면 E2E
# 앞의 셋은 서버 없이, 뒤의 둘은 scripts/start_all.sh 로 띄운 뒤 (Spring demo 프로필 · 시연 상태)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
step() { echo; echo "── $1 ─────────────────────────────"; shift; ( "$@" ) || fail=$((fail + 1)); }
step "AI 단위 테스트 (pytest)"     bash -c "cd '$ROOT/ai' && DATA_SOURCE=csv .venv/bin/python -m pytest -q"
step "Spring 단위 테스트 (gradle)" bash -c "cd '$ROOT/api' && ./gradlew test -q"
step "화면 단위 테스트 (vitest)"   bash -c "cd '$ROOT/web' && npm test --silent"
step "통합 점검 (check_all)"      "$ROOT/ai/.venv/bin/python" "$ROOT/scripts/check_all.py"
step "화면 E2E (Playwright)"      node "$ROOT/scripts/e2e/e2e.mjs"
echo; [ "$fail" -eq 0 ] && echo "모두 통과" || echo "실패한 단계 $fail 개"
exit "$fail"
