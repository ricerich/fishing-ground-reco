"""작업 rag_reindex — 문서를 다시 읽어 rag_doc 표에 넣고, AI 서버에 색인을 다시 만들라고 알린다."""
import os

import requests

from . import config as C
from .rag.corpus import build, store


def reindex() -> dict:
    docs, chunks = build()
    n = store(docs)
    url = os.getenv("AI_BASE_URL", "http://127.0.0.1:8000")
    try:
        r = requests.post(f"{url}/internal/rag/reload", headers={"X-Internal-Token": C.INTERNAL_TOKEN}, timeout=30).json()
    except requests.RequestException:
        r = {"ready": None, "reason": "AI 서버가 꺼져 있음 — 다음 기동 때 읽음"}
    kinds = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {"docs": len(docs), "chunks": len(chunks), "stored": n, "kinds": kinds, "api": r,
            "_summary": f"문서 {len(docs)}개 · 청크 {len(chunks)}개 → 색인 다시 만듦 ("
                        + " · ".join(f"{k} {v}" for k, v in kinds.items()) + ")"}
