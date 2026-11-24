"""문서 → 청크. 문서는 ai/rag_docs 아래 두 갈래
  service/*.md  우리 서비스 설명 (추천 원리 · 근거 숫자 · 모델 교체 · 자료) — 사실은 코드와 같아야 한다
  sample/       실습 U2 의 수업용 문서 (가상 어촌계 수칙 · 현장 용어 · 특보 예시) — 화면에 '수업용 예시'로 보인다
운영에서는 LAW_OC(국가법령 공동활용)로 받은 법령 · 수집한 특보를 같은 모양으로 더하면 된다 (U2 s1_step5).
"""
import json
import re
from pathlib import Path

from .. import config as C

DOCS = C.ROOT / "rag_docs"
MAX = 450                     # 청크 최대 글자 수 — 넘으면 문장 경계에서 자른다


def clean(text):
    """특보 원문은 HTML 조각으로 온다 (U2 1회차) — 태그 · 엔티티를 걷어 내고 줄만 남긴다"""
    import html
    text = re.sub(r"<\s*(br|/p|/div|/li)\s*/?>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def _front(text):
    meta = {}
    if text.startswith("---"):
        head, _, text = text[3:].partition("\n---")
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text.lstrip("-\n ")


def _split_long(body):
    if len(body) <= MAX:
        return [body]
    out, cur = [], ""
    for s in re.split(r"(?<=[.?!])\s+", body):
        if cur and len(cur) + len(s) > MAX:
            out.append(cur.strip())
            cur = ""
        cur += s + " "
    return out + ([cur.strip()] if cur.strip() else [])


def load_docs() -> list[dict]:
    docs = []
    for f in sorted((DOCS / "service").glob("*.md")):
        meta, body = _front(f.read_text(encoding="utf-8"))
        docs.append({"doc_id": f"service-{f.stem}", "kind": meta.get("kind", "service"), "title": meta.get("title", f.stem),
                     "source": "서비스 설명", "date": None, "body": body, "sample": False})
    for f in sorted((DOCS / "sample").glob("*.md")):
        meta, body = _front(f.read_text(encoding="utf-8"))
        title = body.splitlines()[0].lstrip("# ").strip()
        kind = "rule" if "수칙" in title else "guide"
        docs.append({"doc_id": f"{kind}-{f.stem}", "kind": kind, "title": title, "source": "수업용 예시(U2)", "date": None,
                     "body": body, "sample": True})
    for f in sorted((DOCS / "sample").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                docs.append({"doc_id": r["doc_id"], "kind": "alert", "title": r["title"], "source": r.get("source", "특보"),
                             "date": r.get("date"), "body": clean(r["text"]), "sample": True})
    return docs


def chunk(doc) -> list[dict]:
    """서비스 설명 · 용어 = '## 제목' 마다, 수칙 = '제N조' 마다, 특보 = 통째로. 긴 덩어리는 문장 경계에서 다시 자른다."""
    body = doc["body"]
    if doc["kind"] == "rule":
        parts = [("", p) for p in re.split(r"\n(?=제\d+조)", body) if p.strip()]
    elif doc["kind"] == "alert":
        parts = [("", body)]
    else:
        parts, head = [], ""
        for block in re.split(r"\n(?=#{2,3} )", body):
            lines = block.strip().splitlines()
            if lines and lines[0].startswith("#"):
                head = lines[0].lstrip("# ").strip()
                block = "\n".join(lines[1:])
            if block.strip():
                parts.append((head, block.strip()))
    out = []
    for sec, text in parts:
        m = re.match(r"(제\d+조\([^)]*\))", text)
        sec = sec or (m.group(1) if m else doc["title"])
        for piece in _split_long(text.strip()):
            out.append({"chunk_id": f"{doc['doc_id']}#{len(out) + 1:02d}", "doc_id": doc["doc_id"], "kind": doc["kind"],
                        "title": doc["title"], "section": sec, "text": piece, "sample": doc["sample"], "date": doc["date"]})
    return out


def build() -> tuple[list[dict], list[dict]]:
    docs = load_docs()
    return docs, [c for d in docs for c in chunk(d)]


def store(docs):
    """rag_doc 표에 문서 단위로 (관리 · 감사용). 검색은 메모리 색인으로 한다 (문서가 수백 개 수준)."""
    from ..db import connect, upsert
    with connect() as c:
        n = upsert(c, "rag_doc", ["doc_id", "kind", "title", "source", "doc_date", "body", "meta"],
                   [(d["doc_id"], d["kind"], d["title"][:200], d["source"][:100], d["date"], d["body"],
                     json.dumps({"sample": d["sample"]}, ensure_ascii=False)) for d in docs], ["doc_id"])
        c.commit()
    return n
