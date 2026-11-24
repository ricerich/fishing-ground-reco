"""3단계 — 수집 방식 고르기 · 요약 줄 (DB 없이 도는 단위 테스트)"""
from reco import collect_all
from reco import config as C


def test_mode_replay_without_key_or_in_demo(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_KEY", "")
    assert collect_all.mode() == "replay"
    monkeypatch.setenv("DATA_GO_KR_KEY", "x")
    monkeypatch.setattr(C, "DEMO_TODAY", "2026-10-15")
    assert collect_all.mode() == "replay"          # 키가 있어도 시연 날짜면 OpenAPI 를 부르지 않는다
    monkeypatch.setattr(C, "DEMO_TODAY", "")
    assert collect_all.mode() == "live"


def test_finish_counts_failures_and_keeps_status_ok_when_partly_failed():
    out = {"mode": "replay", "from": "2026-10-08", "to": "2026-10-14",
           "auction": {"재생": 20, "없음": 1}, "khoa": {"재생": 70, "실패": 28}, "sea_forecast": "재생",
           "fishing_index": "재생", "load": {"auction_daily": 47766}}
    r = collect_all._finish(out, 0)
    assert r["counts"]["실패"] == 28
    assert "성공 93/121" in r["_summary"] and "실패 28" in r["_summary"]
    assert r["_status"] == "ok"                     # 일부 실패는 작업 실패가 아니다 — 조건 1 이 판단한다


def test_all_failed_is_job_failure():
    out = {"mode": "live", "from": "a", "to": "b", "auction": {"실패": 3}, "khoa": {"실패": 2},
           "sea_forecast": "실패", "fishing_index": "실패", "load": {}}
    assert collect_all._finish(out, 0)["_status"] == "fail"
