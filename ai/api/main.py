"""AI 서버 (FastAPI :8000) — 외부에 공개하지 않는다. Spring 만 X-Internal-Token 헤더를 붙여 부른다.

  uvicorn api.main:app --host 127.0.0.1 --port 8000

경로
  GET  /health                         누구나(로컬) — 챔피언 · 자료 마지막 날 · RAG 준비 상태
  GET  /internal/recommend             임의 날짜 즉석 추천 (관리 · 디버그용, 화면은 미리 계산한 표를 읽는다)
  POST /internal/models/reload         챔피언 다시 읽기 (작업 프로세스가 교체 뒤 부른다)
  POST /internal/jobs/{name}           작업 요청 → job_queue (실행은 작업 프로세스)
  GET  /internal/jobs/queue/{id}       요청 상태
  (4단계) POST /internal/rag/ask · /internal/rag/explain
"""
import json
from contextlib import asynccontextmanager
from datetime import date

from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from reco import config as C
from reco import registry
from reco.db import connect

ALLOWED_JOBS = {"collect_daily", "precompute_today", "evaluate_live", "retrain_weekly", "rollback", "rag_reindex"}
STATE: dict = {}


def load_state():
    registry._cache.clear()
    try:
        champ = registry.champion()
        STATE.update(champion=champ, champion_kind=registry.load(champ)[1].get("kind"), db="ok")
    except Exception as e:  # noqa: BLE001 — DB 가 꺼져 있어도 서버는 뜨고 health 에 이유를 보인다
        STATE.update(champion=None, db=f"error: {type(e).__name__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_state()
    from api import rag_routes
    rag_routes.startup(STATE)
    yield


app = FastAPI(title="어장 추천 AI 서버", version="1.0", lifespan=lifespan, docs_url=None,
              description="Spring(api) 만 부르는 내부 API. 모든 /internal 경로는 X-Internal-Token 이 필요하다.")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/docs", include_in_schema=False)
def docs():
    """Swagger 화면 — CDN 대신 저장소의 파일로 (강의실 · 캡처에서 인터넷이 없어도 보이게)"""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="어장 추천 AI 서버 — 문서",
                               swagger_js_url="/static/swagger/swagger-ui-bundle.js",
                               swagger_css_url="/static/swagger/swagger-ui.css", swagger_favicon_url="")


def internal(x_internal_token: str | None = Header(default=None)):
    if not C.INTERNAL_TOKEN:
        raise HTTPException(503, "INTERNAL_TOKEN 이 설정되지 않아 내부 API 를 열지 않습니다")
    if x_internal_token != C.INTERNAL_TOKEN:
        raise HTTPException(401, "내부 토큰이 맞지 않습니다")


def last_day():
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT MAX(sale_date) FROM auction_daily")
        return cur.fetchone()[0]


@app.get("/health")
def health():
    try:
        ld = last_day()
    except Exception as e:  # noqa: BLE001
        ld, STATE["db"] = None, f"error: {type(e).__name__}"
    return {"status": "ok" if STATE.get("db") == "ok" else "degraded", "service": "ai", "today": str(C.today()),
            "demo": bool(C.DEMO_TODAY), "champion": STATE.get("champion"), "champion_kind": STATE.get("champion_kind"),
            "data_last_day": str(ld) if ld else None, "db": STATE.get("db"), "rag": STATE.get("rag", {"ready": False})}


@app.get("/internal/recommend", dependencies=[Depends(internal)])
def recommend_now(species: str = Query(..., description="고등어 · 방어 · 삼치"), date_: date | None = Query(None, alias="date"),
                  k: int = Query(3, ge=1, le=14), version: str | None = None):
    if species not in C.SPECIES:
        raise HTTPException(400, f"품목은 {C.SPECIES} 중 하나")
    from reco import precompute
    D = pd.Timestamp(date_ or C.today())
    ld = pd.Timestamp(last_day())
    if D > ld + pd.Timedelta(days=1):
        raise HTTPException(422, f"{(ld + pd.Timedelta(days=1)).date()} 까지 추천할 수 있음 (위판 자료가 {ld.date()} 까지)")
    v = version or STATE.get("champion") or registry.RULE
    res, _ = precompute.compute([D], [v])
    r = res.get((D, species, v), {"items": [], "excluded": [], "candidates": 0})
    return {"species": species, "date": str(D.date()), "model": v, "k": k, "candidates": r["candidates"],
            "items": r["items"][:k], "excluded": r["excluded"]}


@app.post("/internal/models/reload", dependencies=[Depends(internal)])
def reload_models():
    load_state()
    return {"champion": STATE.get("champion")}


class JobReq(BaseModel):
    requested_by: str = Field(..., max_length=80)
    params: dict = Field(default_factory=dict)


@app.post("/internal/jobs/{name}", dependencies=[Depends(internal)], status_code=202)
def enqueue(name: str, req: JobReq):
    if name not in ALLOWED_JOBS:
        raise HTTPException(400, f"요청할 수 있는 작업: {sorted(ALLOWED_JOBS)}")
    if name == "rollback" and not req.params.get("version"):
        raise HTTPException(422, "rollback 에는 params.version 이 필요합니다")
    with connect() as c, c.cursor() as cur:
        cur.execute("INSERT INTO job_queue (job, params, requested_by, requested_at) VALUES (%s,%s,%s,%s)",
                    (name, json.dumps(req.params, ensure_ascii=False), req.requested_by, C.now().replace(tzinfo=None)))
        c.commit()
        qid = cur.lastrowid
    return {"queue_id": qid, "job": name, "status": "queued"}


@app.get("/internal/jobs/queue/{qid}", dependencies=[Depends(internal)])
def queue_status(qid: int):
    with connect() as c, c.cursor() as cur:
        cur.execute("""SELECT q.queue_id, q.job, q.status, q.run_id, r.summary FROM job_queue q
                       LEFT JOIN job_run r ON r.run_id = q.run_id WHERE q.queue_id=%s""", (qid,))
        r = cur.fetchone()
    if not r:
        raise HTTPException(404, "없는 요청")
    return dict(zip(["queue_id", "job", "status", "run_id", "summary"], r))
