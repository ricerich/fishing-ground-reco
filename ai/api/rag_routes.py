"""RAG 경로 (4단계) — 모두 내부용(X-Internal-Token). 답은 NDJSON 스트림: 한 줄에 이벤트 하나 (reco/rag/answer.py)

  POST /internal/rag/ask      {question, history?}        규정 · 용어 · 서비스 문답
  POST /internal/rag/explain  {species, date, area}       '왜 이 권역인가요?' — 숫자는 추천 표에서
  POST /internal/rag/reload                               색인 다시 만들기 (rag_reindex 작업 뒤)
  GET  /internal/rag/search?q=                            검색만 (실습 · 디버그)
"""
import json
import time
from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from reco import config as C
from reco.rag import answer, llm

STATE_REF: dict = {}
_llm_cache = {"at": 0.0, "v": None}


def startup(state: dict):
    STATE_REF["s"] = state
    try:
        s = answer.load()
        state["rag"] = {"ready": True, "docs": s["docs"], "chunks": len(s["chunks"]), "llm": llm.name()}
    except Exception as e:  # noqa: BLE001 — 색인이 안 돼도 추천 서비스는 떠야 한다
        state["rag"] = {"ready": False, "reason": f"{type(e).__name__}: {e}"[:200]}


def llm_status():
    if time.time() - _llm_cache["at"] > 30:                      # health 를 자주 불러도 Ollama 를 30초에 한 번만 확인
        _llm_cache.update(at=time.time(), v=llm.status())
    return _llm_cache["v"]


def router(internal) -> APIRouter:
    r = APIRouter(prefix="/internal/rag", dependencies=[Depends(internal)], tags=["rag"])

    def ndjson(gen):
        def lines():
            for ev in gen:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        return StreamingResponse(lines(), media_type="application/x-ndjson")

    class Turn(BaseModel):
        role: str
        content: str = Field(..., max_length=1200)

    class AskReq(BaseModel):
        question: str = Field(..., min_length=2, max_length=300)
        history: list[Turn] = Field(default_factory=list, max_length=8)

    class ExplainReq(BaseModel):
        species: str
        date: Date
        area: str = Field(..., max_length=20)

    @r.post("/ask")
    def ask(req: AskReq):
        return ndjson(answer.ask(req.question.strip(), [t.model_dump() for t in req.history]))

    @r.post("/explain")
    def explain(req: ExplainReq):
        if req.species not in C.SPECIES:
            raise HTTPException(400, f"품목은 {C.SPECIES} 중 하나")
        return ndjson(answer.explain(req.species, req.date, req.area))

    @r.post("/reload")
    def reload():
        startup(STATE_REF.get("s", {}))
        return STATE_REF["s"]["rag"]

    @r.get("/search")
    def search(q: str, k: int = 4):
        if answer.STATE["index"] is None:
            answer.load()
        return [{k_: h[k_] for k_ in ("chunk_id", "title", "section", "kind", "score", "text")} for h in answer.STATE["index"].search(q, k=k)]

    return r
