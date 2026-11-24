"""질문 → 검색 → 프롬프트 → LLM 스트림 → 검사. 화면으로 가는 이벤트(NDJSON 한 줄씩):

  {"type":"meta",   "llm":"ollama:qwen3:1.7b", "sources":[{id,title,section,kind,sample,text}], "facts": "...?"}
  {"type":"notice", "text":"Ollama 에 연결할 수 없어 근거 문장만 보여 드립니다"}   (바꿔 탈 때만)
  {"type":"delta",  "text":"..."}  … 여러 번
  {"type":"done",   "check":{cited, made_up, cite_ok, said_unknown, numbers_ok, unknown_numbers}, "llm":"…", "seconds":1.2}
"""
import json
import re
import time

from .. import config as C  # noqa: F401 — .env 를 먼저 읽게
from . import llm
from .corpus import build
from .search import Hybrid

UNKNOWN = "제공된 자료에서 찾을 수 없습니다."
STATE = {"index": None, "chunks": [], "docs": 0}

SYSTEM_ASK = f"""당신은 어장 추천 서비스의 안내원입니다. 어민의 질문에 답합니다.
규칙
1. <근거> 안의 내용만 씁니다. 근거에 없는 사실이나 숫자를 지어내지 않습니다.
2. 쓴 근거의 번호를 문장 끝에 대괄호로 붙입니다. 예: 평소의 1.5배 이상이면 좋은 날입니다 [service-01_recommend#02]
3. 근거로 답할 수 없으면 다른 말 없이 정확히 "{UNKNOWN}" 라고만 답합니다.
4. '수업용 예시' 문서는 실제 법령 · 규약이 아니므로, 그 문서를 쓰면 '수업용 예시 문서에 따르면'이라고 밝힙니다.
5. 4문장 이내, 존댓말."""

SYSTEM_EXPLAIN = """당신은 어장 추천 서비스의 안내원입니다. 왜 이 권역이 이 순위인지 어민에게 설명합니다.
규칙
1. 숫자는 <추천> 블록에 적힌 것만, 적힌 그대로 씁니다. 계산하거나 반올림을 바꾸거나 새 숫자를 만들지 않습니다.
2. <추천> 에서 온 내용은 문장 끝에 [추천], <근거> 에서 온 내용은 그 번호를 붙입니다.
3. 순서: ① 순위와 가장 큰 이유(위판 흐름) ② 바다 관측 ③ 경고가 있으면 경고 ④ 점수를 확률로 읽지 말라는 한 문장.
4. 잡힌다고 장담하지 않습니다. '평소보다 많이 팔릴 가능성이 높은 권역'이라고 말합니다.
5. 5문장 이내, 존댓말."""


def load():
    docs, chunks = build()
    STATE.update(index=Hybrid(chunks), chunks=chunks, docs=len(docs))
    return STATE


def _src(h):
    return {"id": h["chunk_id"], "title": h["title"], "section": h["section"], "kind": h["kind"], "sample": h["sample"],
            "text": h["text"][:400]}


def _context(hits):
    return "<근거>\n" + "\n\n".join(
        f"[{h['chunk_id']}] {h['title']} · {h['section']}{' (수업용 예시)' if h['sample'] else ''}\n{h['text']}" for h in hits) + "\n</근거>"


NUM = re.compile(r"(?<![\w.])[-+−]?\d+(?:[.,]\d+)?")
CITE = re.compile(r"\[([^\[\]\s]+#\d+|추천)\]")       # 문서 번호(…#03) 나 [추천] 만 인용으로 본다


def _nums(s):
    return {n.replace(",", "").replace("−", "-").lstrip("+") for n in NUM.findall(s)}


def check(answer, hits, allowed_text, facts=False):
    ids = {h["chunk_id"] for h in hits} | ({"추천"} if facts else set())
    cited = CITE.findall(answer)
    allowed = _nums(allowed_text)
    allowed |= {a.lstrip("-") for a in allowed} | {str(int(float(a))) for a in allowed if re.fullmatch(r"-?\d+\.0+", a)}
    unknown = sorted(n for n in _nums(re.sub(r"\[[^\]]*\]", "", answer)) if n.lstrip("-") not in allowed and n not in allowed)
    return {"cited": cited, "made_up": [c for c in cited if c not in ids], "cite_ok": bool(cited) and all(c in ids for c in cited),
            "said_unknown": "찾을 수 없" in answer, "numbers_ok": not unknown, "unknown_numbers": unknown[:8]}


def _run(messages, fallback_text, meta, hits, allowed_text, facts=False):
    t0 = time.time()
    yield meta
    out, used = [], meta["llm"]
    try:
        if meta["llm"] == "mock":
            raise llm.LLMUnavailable("mock")
        for piece in llm.stream(messages):
            out.append(piece)
            yield {"type": "delta", "text": piece}
    except llm.LLMUnavailable as e:
        if out:                                                  # 중간에 끊김 — 받은 데까지만
            yield {"type": "notice", "text": f"LLM 응답이 중간에 끊겼습니다: {e}"}
        else:
            used = "mock"
            if str(e) != "mock":
                yield {"type": "notice", "text": f"{e} — LLM 없이 근거 문장으로 답합니다."}
            for w in re.findall(r"\S+\s*", fallback_text):
                out.append(w)
                yield {"type": "delta", "text": w}
                time.sleep(0.015)                                 # 흘려보내는 모양을 맞춘다 (화면 · 캡처)
    answer = "".join(out).strip()
    yield {"type": "done", "answer": answer, "check": check(answer, hits, allowed_text, facts), "llm": used,
           "seconds": round(time.time() - t0, 2)}


# ── 규정 · 용어 · 서비스 문답 ───────────────────────────────────────

def ask(question: str, history=None):
    if STATE["index"] is None:
        load()
    hits = STATE["index"].search(question, k=4)
    msgs = [{"role": "system", "content": SYSTEM_ASK}]
    for h in (history or [])[-4:]:                                # 앞 대화는 맥락으로만 (근거는 새로 찾는다)
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:600]})
    msgs.append({"role": "user", "content": _context(hits) + f"\n\n질문: {question}"})
    meta = {"type": "meta", "mode": "ask", "llm": llm.name(), "sources": [_src(h) for h in hits]}
    fb = _extract(question, hits)
    yield from _run(msgs, fb, meta, hits, _context(hits) + question)


# 어디에나 나오는 낱말 — 겹쳐도 근거라고 보지 않는다 (품목 이름은 서비스 문서마다 나온다)
WEAK = {"하", "되", "있", "없", "이", "보이", "보", "않", "같", "어떻", "왜", "무엇", "뭐", "언제", "고등어", "방어", "삼치", "어장", "추천", "알", "오늘"}


def _extract(question, hits):
    """mock: 검색 1 · 2위 청크에서 질문 낱말이 많이 겹치는 문장 두 개를 골라 번호를 붙인다 (생성하지 않음)"""
    if not hits:
        return UNKNOWN
    from .search import tokens
    q = set(tokens(question)) - WEAK
    cands = []
    for h in hits[:2]:
        for s in re.split(r"(?<=[.?!])\s+|\n+", h["text"]):
            s = s.strip(" -·")
            if len(s) > 12:
                ctx = set(tokens(f"{h['title']} {h['section']} {s}"))          # 제목 · 조문 이름까지 겹침으로 센다
                cands.append((len(q & ctx) + 0.1 * len(q & set(tokens(s))), s, h["chunk_id"], h["sample"]))
    cands.sort(key=lambda x: -x[0])
    pick = [c for c in cands[:2] if c[0] >= 1]                    # 뜻 있는 낱말이 하나도 안 겹치면 근거가 아니다
    if not pick:
        return UNKNOWN
    lead = "수업용 예시 문서에 따르면 " if any(p[3] for p in pick) else ""
    return lead + " ".join(f"{s.rstrip('.')}. [{cid}]" for _, s, cid, _ in pick)


# ── 추천 근거 설명 ────────────────────────────────────────────────

def facts_for(species, date, area):
    from ..db import connect
    with connect() as c, c.cursor() as cur:
        cur.execute("""SELECT r.rnk, r.score, r.usual_kg, r.reasons, r.warnings, r.feats, r.model_version, rr.candidates
                       FROM recommendation r JOIN rec_run rr ON rr.rec_date=r.rec_date AND rr.species=r.species
                            AND rr.served_version=r.model_version
                       JOIN area a ON a.area_id=r.area_id
                       WHERE r.rec_date=%s AND r.species=%s AND a.area_name=%s""", (date, species, area))
        row = cur.fetchone()
        if not row:
            cur.execute("""SELECT e.reason FROM recommendation_excluded e JOIN rec_run rr ON rr.rec_date=e.rec_date
                           AND rr.species=e.species AND rr.served_version=e.model_version JOIN area a ON a.area_id=e.area_id
                           WHERE e.rec_date=%s AND e.species=%s AND a.area_name=%s""", (date, species, area))
            ex = cur.fetchone()
            return None, (f"{area} 은(는) 이날 순위에서 빠졌습니다 — {ex[0]}" if ex else "그날 그 권역의 추천이 없습니다")
        cur.execute("""SELECT a.area_name FROM recommendation r JOIN rec_run rr ON rr.rec_date=r.rec_date AND rr.species=r.species
                       AND rr.served_version=r.model_version JOIN area a ON a.area_id=r.area_id
                       WHERE r.rec_date=%s AND r.species=%s ORDER BY r.rnk LIMIT 3""", (date, species))
        top3 = [r[0] for r in cur.fetchall()]
    rnk, score, usual, reasons, warnings, feats, version, cands = row
    f = json.loads(feats or "{}")
    reasons, warnings = json.loads(reasons or "[]"), json.loads(warnings or "[]")

    def v(x, d=1, unit=""):
        return "모름" if x is None else f"{x:.{d}f}{unit}"
    anom = f.get("wtem_anom")
    lines = [f"[추천] {date} {species} {area} — 후보 {cands}곳 중 {rnk}위 (점수 {float(score):.2f}, 모델 {version})",
             f"- 평소 위판: {usual:,}kg (어제까지 최근 28일 중 위판한 날의 중앙값)",
             f"- 어제 위판: 평소의 {v(f.get('rel_lag1'))}배 · 최근 7일 평균: 평소의 {v(f.get('rel_mean7'))}배 · "
             f"최근 7일 중 위판한 날: {v(f.get('sold_days7'), 0)}일",
             f"- 어제 수온: {v(f.get('wtem'), 1, '℃')} · 평년보다 {'모름' if anom is None else f'{anom:+.1f}℃'} · "
             f"어제 최대 돌풍: {v(f.get('gust_lag1'), 0, 'm/s')}",
             f"- 모델이 꼽은 근거: {' / '.join(reasons) if reasons else '없음'}",
             f"- 경고: {' / '.join(warnings) if warnings else '없음'}",
             f"- 같은 날 Top-3: {', '.join(top3)}"]
    return {"text": "<추천>\n" + "\n".join(lines) + "\n</추천>", "rank": rnk, "feats": f, "reasons": reasons,
            "warnings": warnings, "usual": usual, "score": float(score), "version": version, "cands": cands}, None


def explain(species, date, area):
    if STATE["index"] is None:
        load()
    facts, err = facts_for(species, str(date), area)
    if err:
        yield {"type": "meta", "mode": "explain", "llm": llm.name(), "sources": [], "facts": None}
        yield {"type": "delta", "text": err}
        yield {"type": "done", "answer": err, "check": {"numbers_ok": True, "cited": [], "made_up": [], "cite_ok": False,
                                                          "said_unknown": False, "unknown_numbers": []}, "llm": "none", "seconds": 0}
        return
    q = "추천 순위 근거 어제 위판 배수 평소 점수 확률 " + " ".join(facts["reasons"] + facts["warnings"])
    hits = STATE["index"].search(q, k=3, kinds={"service"})
    score_chunk = next((c for c in STATE["chunks"] if c["section"] == "점수의 뜻"), None)   # '점수 ≠ 확률' 은 늘 근거에
    if score_chunk and all(h["chunk_id"] != score_chunk["chunk_id"] for h in hits):
        hits = hits[:2] + [score_chunk]
    msgs = [{"role": "system", "content": SYSTEM_EXPLAIN},
            {"role": "user", "content": facts["text"] + "\n\n" + _context(hits) + f"\n\n질문: 왜 {area} 이(가) {facts['rank']}위인가요?"}]
    meta = {"type": "meta", "mode": "explain", "llm": llm.name(), "sources": [_src(h) for h in hits], "facts": facts["text"]}
    yield from _run(msgs, _explain_text(area, facts, hits), meta, hits, facts["text"] + _context(hits), facts=True)


def josa(w, a, b):
    c = ord(w[-1]) - 0xAC00
    return w + (a if 0 <= c <= 11171 and c % 28 else b)


def _explain_text(area, f, hits):
    """mock: 숫자를 <추천> 블록에서 그대로 옮겨 만든 고정 문장 (LLM 없이도 같은 뜻을 전한다)"""
    ft = f["feats"]

    def v(x, d=1):
        return "모름" if x is None else f"{x:.{d}f}"
    s = [f"{josa(area, '은', '는')} 후보 {f['cands']}곳 중 {f['rank']}위입니다. 어제 위판이 평소의 {v(ft.get('rel_lag1'))}배, "
         f"최근 7일 평균이 평소의 {v(ft.get('rel_mean7'))}배로 위판 흐름이 가장 큰 이유입니다 [추천]."]
    if ft.get("wtem") is not None:
        a = ft.get("wtem_anom")
        s.append(f"어제 수온은 {v(ft['wtem'])}℃로 평년보다 {'모름' if a is None else f'{a:+.1f}'}℃였습니다 [추천].")
    if f["warnings"]:
        s.append(f"다만 {f['warnings'][0]} [추천].")
    sid = next((h["chunk_id"] for h in hits if h["section"] == "점수의 뜻"), hits[0]["chunk_id"] if hits else None)
    s.append(f"화면의 점수 {f['score']:.2f}는 순서를 매기는 값이지 잡힐 확률이 아닙니다" + (f" [{sid}]." if sid else "."))
    return " ".join(s)
