"""작업 프로세스 — 정해진 시각의 작업 + 관리자 요청(job_queue)을 실행한다. FastAPI 와 따로 띄운다.

  python -m reco.worker

- FastAPI 안에서 돌리지 않는 이유: uvicorn 워커가 여럿이면 같은 작업이 겹치고, 학습 중에는 응답이 느려진다.
- 시연(DEMO_TODAY 설정)에서는 정해진 시각의 작업을 끈다(시연 자료가 바뀌지 않게). 관리자 요청은 언제나 실행.
  WORKER_SCHEDULE=on 으로 강제로 켤 수 있다.
"""
import json
import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import config as C
from . import jobs
from .db import connect

log = logging.getLogger("worker")

SCHEDULE = [  # (작업, cron, 인자) — 시간은 Asia/Seoul
    ("collect_daily", "0 5 * * *", {}),          # 05:00 수집 (05시 해상예보 발표 뒤 받으려면 05:20 으로 늦춰도 됨)
    ("precompute_today", "40 5 * * *", {}),      # 05:40 오늘 추천
    ("evaluate_live", "0 6 * * *", {}),          # 06:00 확정된 날 채점
    ("rag_reindex", "10 6 * * *", {}),           # 06:10 새 특보 문서 색인 (4단계)
    ("collect_daily", "30 18 * * *", {}),        # 18:30 오늘 위판 다시 받기 (내일 추천의 '어제')
    ("retrain_weekly", "0 3 * * mon", {}),       # 월 03:00 재학습 · 평가 · 교체 판단
]


def schedule_on() -> bool:
    v = os.getenv("WORKER_SCHEDULE", "").lower()
    return v == "on" if v else not C.DEMO_TODAY


def safe_run(name, trigger, **kw):
    try:
        out = jobs.run(name, trigger=trigger, **kw)
        log.info("%s %s — %s", name, out.get("status"), out.get("summary"))
        return out
    except Exception as e:  # noqa: BLE001 — 실패는 job_run 에 남았다. 프로세스는 계속 산다
        log.error("%s 실패: %s", name, e)
        return None


def poll_queue():
    """요청을 하나씩 꺼내 실행. 두 워커가 떠도 같은 요청을 두 번 실행하지 않도록 UPDATE … WHERE status='queued'."""
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT queue_id, job, params, requested_by FROM job_queue WHERE status='queued' ORDER BY queue_id LIMIT 1")
        r = cur.fetchone()
        if not r:
            return
        qid, name, params, who = r
        cur.execute("UPDATE job_queue SET status='running' WHERE queue_id=%s AND status='queued'", (qid,))
        c.commit()
        if cur.rowcount == 0:
            return
    kw = json.loads(params) if params else {}
    if name in ("retrain_weekly", "rollback"):
        kw.setdefault("actor", f"admin:{who}")
    out = safe_run(name, f"admin:{who}", **kw)
    with connect() as c, c.cursor() as cur:
        cur.execute("UPDATE job_queue SET status=%s, run_id=%s WHERE queue_id=%s",
                    ("done" if out else "fail", out.get("run_id") if out else _last_run_id(cur, name), qid))
        c.commit()


def _last_run_id(cur, name):
    cur.execute("SELECT MAX(run_id) FROM job_run WHERE job=%s", (name,))
    return cur.fetchone()[0]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sch = BackgroundScheduler(timezone=C.TZ)
    if schedule_on():
        for name, cron, kw in SCHEDULE:
            sch.add_job(safe_run, CronTrigger.from_crontab(cron, timezone=C.TZ), args=[name, "schedule"], kwargs=kw,
                        id=f"{name}@{cron}", max_instances=1, coalesce=True)
        log.info("정해진 작업 %d개 켬", len(SCHEDULE))
    else:
        log.info("시연 모드(DEMO_TODAY=%s) — 정해진 작업은 끔, 관리자 요청만 실행", C.DEMO_TODAY)
    sch.start()
    try:
        while True:
            try:
                poll_queue()
            except Exception as e:  # noqa: BLE001 — DB 가 잠깐 끊겨도 다시 시도
                log.warning("요청 확인 실패: %s", e)
            time.sleep(int(os.getenv("WORKER_POLL_SECONDS", "10")))
    except KeyboardInterrupt:
        sch.shutdown()


if __name__ == "__main__":
    main()
