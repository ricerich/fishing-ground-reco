"""통합 점검 — 네 프로세스와 DB 를 올린 뒤 항목별 OK/FAIL (인공지능 서비스 구현 A6 방식)

  ai/.venv/bin/python scripts/check_all.py           (Windows: ai\\.venv\\Scripts\\python scripts\\check_all.py)

단계가 늘 때마다 항목을 더한다. 실패하면 종료 코드 1.
"""
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

WEB = os.getenv("WEB_BASE_URL", "http://localhost:3000")
API = "http://127.0.0.1:8080"
AI = "http://127.0.0.1:8000"
TOKEN = os.getenv("INTERNAL_TOKEN", "")
results = []


def check(name, fn):
    t = time.time()
    try:
        detail = fn() or ""
        results.append((True, name, detail, time.time() - t))
    except Exception as e:  # noqa: BLE001
        results.append((False, name, f"{type(e).__name__}: {e}"[:160], time.time() - t))


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def j(url, **kw):
    r = requests.get(url, timeout=kw.pop("timeout", 10), **kw)
    r.raise_for_status()
    return r.json()


# ── 0단계: 네 부분이 살아 있나 ──────────────────────────────────────
def ai_health():
    h = j(f"{AI}/health")
    expect(h["status"] == "ok", h)
    return f"챔피언 {h['champion']} · 자료 {h['data_last_day']}"


def ai_token_required():
    r = requests.get(f"{AI}/internal/recommend", params={"species": "방어"}, timeout=10)
    expect(r.status_code == 401, f"토큰 없이 {r.status_code}")
    return "토큰 없이 401"


def api_health():
    h = j(f"{API}/api/health")
    expect(h["appDb"]["status"] == "ok" and h["recoViews"]["status"] == "ok" and h["ai"]["status"] == "ok", h)
    return f"app {h['appDb']['detail']} · reco {h['recoViews']['detail']}"


def web_proxy():
    r = requests.get(f"{WEB}/api/meta", timeout=20)
    r.raise_for_status()
    return f"화면 → Spring 넘김 OK · 오늘 {r.json()['today']}"


# ── 1단계: 추천 조회 ──────────────────────────────────────────────
def reco_today():
    r = j(f"{API}/api/recommendations", params={"species": "방어"})
    expect(r["available"] and len(r["items"]) == 3, r.get("message"))
    expect([i["rank"] for i in r["items"]] == [1, 2, 3], "순위")
    expect(len(r["items"]) + len(r["others"]) + len(r["excluded"]) <= 14, "권역 수")
    return f"1위 {r['items'][0]['area']} · 서비스 {r['run']['servedVersion']}"


def reco_fast():
    t = []
    for _ in range(20):
        s = time.time()
        requests.get(f"{API}/api/recommendations", params={"species": "고등어"}, timeout=10).raise_for_status()
        t.append(time.time() - s)
    p95 = sorted(t)[int(len(t) * 0.95) - 1] * 1000
    expect(p95 < 300, f"p95 {p95:.0f}ms")
    return f"p95 {p95:.0f}ms (기준 300ms)"


def reco_errors():
    r = requests.get(f"{API}/api/recommendations", params={"species": "광어"}, timeout=10)
    expect(r.status_code == 400 and r.json().get("code") == "species", r.text)
    r = requests.get(f"{API}/api/recommendations", params={"species": "방어", "date": "2027-01-01"}, timeout=10).json()
    expect(r["available"] is False and r["message"], r)
    return "없는 품목 400 · 계산 안 된 날 안내문"


def reco_same_as_ai():
    """화면이 읽는 표(미리 계산) = AI 서버가 지금 계산한 결과 — 같은 날 · 같은 모델이면 순위가 같아야 한다"""
    a = j(f"{API}/api/recommendations", params={"species": "삼치"})
    b = j(f"{AI}/internal/recommend", params={"species": "삼치", "date": a["date"], "version": a["run"]["servedVersion"]},
          headers={"X-Internal-Token": TOKEN})
    expect([i["area"] for i in a["items"]] == [i["area"] for i in b["items"]], (a["items"], b["items"]))
    return "미리 계산 = 즉석 계산 (Top-3 일치)"


def protected():
    r = requests.get(f"{API}/api/me", timeout=10)
    expect(r.status_code == 401, r.status_code)
    return "로그인 없이 /api/me 401"


CHECKS = [
    ("AI 서버 health", ai_health), ("AI 내부 API 는 토큰 필요", ai_token_required), ("Spring health (DB · 뷰 · AI)", api_health),
    ("화면 → Spring 주소 넘김", web_proxy),
    ("오늘 추천 (방어 Top-3)", reco_today), ("추천 응답 속도", reco_fast), ("추천 오류 처리", reco_errors),
    ("미리 계산 = 즉석 계산", reco_same_as_ai), ("보호된 경로", protected),
]

if __name__ == "__main__":
    for name, fn in CHECKS:
        check(name, fn)
    w = max(len(n) for _, n, _, _ in results)
    for ok, name, detail, sec in results:
        print(f"{'OK  ' if ok else 'FAIL'}  {name:<{w}}  {detail}")
    bad = sum(not r[0] for r in results)
    print(f"\n{len(results) - bad}/{len(results)} OK")
    sys.exit(1 if bad else 0)
