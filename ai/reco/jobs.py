"""작업 목록 — 스케줄러(worker) · 관리자 수동 실행 · CLI 가 모두 이 함수들을 부른다 (수동 = 자동, U1-04 원칙)

  python -m reco.jobs list
  python -m reco.jobs run precompute_today
  python -m reco.jobs run retrain_weekly --as-of 2026-10-15
  python -m reco.jobs run bootstrap_demo          # 처음 한 번: 시연 자료 적재 · reco_v1 · 지난 추천 · 성적

작업마다 job_run 표에 한 줄(시작 · 끝 · 상태 · 한 줄 요약 · 자세한 JSON)이 남는다. 실패해도 남는다.
"""
import argparse
import json
import sys
import traceback

import pandas as pd

from . import config as C
from .db import connect

JOBS = {}


def job(name, desc):
    def deco(fn):
        JOBS[name] = {"fn": fn, "desc": desc}
        return fn
    return deco


def _start(name, trigger):
    with connect() as c, c.cursor() as cur:
        cur.execute("INSERT INTO job_run (job, trigger_by, started_at, status) VALUES (%s,%s,%s,'running')",
                    (name, trigger[:60], C.now().replace(tzinfo=None)))
        c.commit()
        return cur.lastrowid


def _end(run_id, status, summary, detail):
    with connect() as c, c.cursor() as cur:
        cur.execute("UPDATE job_run SET ended_at=%s, status=%s, summary=%s, detail=%s WHERE run_id=%s",
                    (C.now().replace(tzinfo=None), status, (summary or "")[:300],
                     json.dumps(detail, ensure_ascii=False, default=str), run_id))
        c.commit()


def run(name, trigger="cli", **kw) -> dict:
    if name not in JOBS:
        raise KeyError(f"없는 작업: {name} (가능: {', '.join(JOBS)})")
    rid = _start(name, trigger)
    try:
        out = JOBS[name]["fn"](**kw) or {}
        status = out.pop("_status", "ok")
        summary = out.pop("_summary", "")
        _end(rid, status, summary, out)
        return {"run_id": rid, "status": status, "summary": summary, **out}
    except Exception as e:                                     # noqa: BLE001 — 실패도 기록하고 다시 던진다
        _end(rid, "fail", f"{type(e).__name__}: {e}"[:300], {"traceback": traceback.format_exc()[-4000:]})
        raise


# ── 작업들 ─────────────────────────────────────────────────────────

@job("collect_daily", "위판(최근 7일 다시) · 권역 관측 14곳 · 낚시지수 · 해상예보 수집 → DB 적재")
def collect_daily(days=None):
    from . import collect_all
    return collect_all.run(days=days)


@job("precompute_today", "오늘(DEMO_TODAY 또는 실제 오늘) 추천을 챔피언 · 규칙으로 계산해 저장")
def precompute_today(date=None):
    from . import precompute
    D = pd.Timestamp(date or C.today())
    r = precompute.run([D])
    return {**r, "_summary": f"{D.date()} 3품목 · 서비스 {r['served']} · 추천 {r['recommendation']}행"}


@job("precompute_range", "기간을 한 번에 다시 계산 (지난 추천 채우기)")
def precompute_range(start, end):
    from . import precompute
    dates = pd.date_range(start, end)
    r = precompute.run(list(dates))
    return {"days": len(dates), "served": r["served"], "_summary": f"{start} ~ {end} {len(dates)}일 · 서비스 {r['served']}"}


@job("evaluate_live", "라벨이 확정된 날의 지난 추천을 채점 (모델 · 규칙)")
def evaluate_live(since=None):
    from . import evaluate
    r = evaluate.run(since)
    return {**r, "_summary": f"채점 {r['evaluated']}건 · 확정된 마지막 날 {r['matured_end']}"}


@job("retrain_weekly", "후보 학습 → 같은 창에서 평가 → 교체 조건 5개 → 교체 또는 거절 → 교체되면 오늘 추천 다시 계산")
def retrain_weekly(as_of=None, actor="auto", dry_run=False):
    from . import retrain
    r = retrain.run(as_of=as_of, actor=actor, dry_run=dry_run)
    out = json.loads(retrain.to_json(r))
    if r["passed"] and not dry_run:
        from . import precompute
        precompute.run([pd.Timestamp(C.today())])
        out["recomputed_today"] = True
        _reload_api()
    out["_summary"] = retrain.summary_line(r)
    return out


@job("rollback", "관리자 되돌리기 — 지정한 버전을 다시 챔피언으로 → 오늘 추천 다시 계산")
def rollback(version, actor="admin"):
    from . import precompute, retrain
    prev = retrain.rollback(version, actor)
    precompute.run([pd.Timestamp(C.today())])
    _reload_api()
    return {"from": prev, "to": version, "_summary": f"{prev} → {version} (되돌리기)"}


@job("bootstrap_demo", "시연 자료 적재 → reco_v1(P6 방식) 챔피언 등록 → 7/1 ~ 오늘 추천 채우기 → 성적 채점")
def bootstrap_demo(backfill_from="2026-07-01"):
    from . import bootstrap
    return bootstrap.run(backfill_from)


@job("rag_reindex", "새 특보 · 문서를 RAG 색인에 더한다 (4단계)")
def rag_reindex():
    try:
        from .rag_index import reindex
    except ImportError:
        return {"_status": "skipped", "_summary": "RAG 는 4단계에서 연결"}
    return reindex()


def _reload_api():
    """FastAPI 가 떠 있으면 챔피언을 다시 읽게 한다 (꺼져 있으면 다음 기동 때 읽음)."""
    import os
    import requests
    url = os.getenv("AI_BASE_URL", "http://127.0.0.1:8000")
    try:
        requests.post(f"{url}/internal/models/reload", headers={"X-Internal-Token": C.INTERNAL_TOKEN}, timeout=5)
    except requests.RequestException:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m reco.jobs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("name")
    r.add_argument("--as-of")
    r.add_argument("--date")
    r.add_argument("--start")
    r.add_argument("--end")
    r.add_argument("--version")
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for k, v in JOBS.items():
            print(f"{k:18s} {v['desc']}")
        return
    kw = {}
    if a.as_of:
        kw["as_of"] = a.as_of
    if a.date:
        kw["date"] = a.date
    if a.start:
        kw["start"], kw["end"] = a.start, a.end
    if a.version:
        kw["version"] = a.version
    if a.dry_run:
        kw["dry_run"] = True
    out = run(a.name, trigger="cli", **kw)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str)[:4000])


if __name__ == "__main__":
    sys.exit(main())
