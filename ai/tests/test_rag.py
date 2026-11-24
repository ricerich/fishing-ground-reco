"""4단계 RAG — 검색 · 답 검사 · LLM 없이 답하기 (DB · LLM 없이 도는 단위 테스트)"""
from reco.rag import answer as A
from reco.rag.corpus import build


def setup_module():
    A.load()


def test_corpus_chunks_have_ids_and_sample_flag():
    docs, chunks = build()
    assert any(d["doc_id"].startswith("service-") for d in docs)
    assert all("#" in c["chunk_id"] for c in chunks)
    assert any(c["sample"] for c in chunks) and any(not c["sample"] for c in chunks)


def test_search_finds_score_meaning():
    hits = A.STATE["index"].search("점수가 확률인가요", k=3)
    assert any(h["section"] == "점수의 뜻" for h in hits)


def test_check_flags_made_up_number_and_citation():
    hits = [c for c in A.STATE["chunks"] if "잘 잡힌 날" in c["section"]]
    ctx = A._context(hits)
    good = f"평소의 1.5배 이상이면 좋은 날입니다 [{hits[0]['chunk_id']}]"
    bad = "평소의 2.7배면 좋은 날입니다 [service-99_none#01]"
    assert A.check(good, hits, ctx)["numbers_ok"] is True
    c = A.check(bad, hits, ctx)
    assert c["numbers_ok"] is False and "2.7" in c["unknown_numbers"]
    assert c["made_up"] == ["service-99_none#01"] and c["cite_ok"] is False


def test_extract_says_unknown_when_nothing_matches():
    hits = A.STATE["index"].search("고등어 금어기", k=4)
    assert A._extract("고등어 금어기는 언제예요?", hits) == A.UNKNOWN


def test_ask_stream_shape_without_llm(monkeypatch):
    monkeypatch.setattr(A.llm, "name", lambda backend=None: "mock")
    ev = list(A.ask("모델은 언제 바뀌나요?"))
    assert ev[0]["type"] == "meta" and ev[-1]["type"] == "done"
    assert "".join(e["text"] for e in ev if e["type"] == "delta").strip() == ev[-1]["answer"]
    assert ev[-1]["check"]["cite_ok"]


def test_josa():
    assert A.josa("여수·고흥", "은", "는") == "여수·고흥은" and A.josa("부산", "은", "는") == "부산은" and A.josa("통영·거제", "은", "는") == "통영·거제는"
