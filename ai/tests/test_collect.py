"""수집기 규칙 검사 (네트워크 없이) — python -m pytest -q"""
import datetime as dt

import numpy as np
import pandas as pd

from reco.collect import sea_forecast as sf
from reco.collect.khoa import _clean
from reco.markets import area_of


def test_slot_05_issue():
    assert sf.slot(202610140500, 0) == (dt.date(2026, 10, 14), "오전")
    assert sf.slot(202610140500, 1) == (dt.date(2026, 10, 14), "오후")
    assert sf.slot(202610140500, 2) == (dt.date(2026, 10, 15), "오전")


def test_slot_17_issue():
    assert sf.slot(202610141700, 0) == (dt.date(2026, 10, 14), "오후")
    assert sf.slot(202610141700, 1) == (dt.date(2026, 10, 15), "오전")


def test_every_area_has_forecast_code():
    from reco.markets import areas_table
    assert set(areas_table()["area"]) == set(sf.REG)


def test_area_of():
    assert area_of("부산시수산업협동조합") == "부산"
    assert area_of("영덕북부수산업협동조합") == "포항·영덕"
    assert area_of("보령수산업협동조합") is None          # 서해 — 프로젝트 밖


def test_khoa_clean_rules():
    idx = pd.date_range("2025-07-01", periods=48, freq="h")
    h = pd.DataFrame({"wtem": 22.0, "artmp": 25.0, "atmpr": 1010.0, "wspd": 2.0, "maxMmntWspd": 3.0,
                      "wndrct": 180.0, "bscTdlvHgt": 150.0, "slntQty": 33.0}, index=idx)
    h.iloc[5, 0] = 0.0          # 고장 0.0
    h.iloc[10, 0] = 26.0        # 한 시간 튐
    h.iloc[20:23, 1] = -39.6    # 부산 기온 −39.6℃ 세 시간 (실제)
    h.iloc[30:34, 0] = 30.5     # 묵호처럼 몇 시간 높았다 떨어짐 (중앙값에서 3℃ 넘게)
    c = _clean(h)
    assert np.isnan(c.iloc[5, 0]) and np.isnan(c.iloc[10, 0])
    assert c.iloc[20:23, 1].isna().all()
    assert c.iloc[30:34, 0].isna().all()


def test_snapshot_parses_real_response(monkeypatch, tmp_path):
    """강사 PC 에서 받은 실제 응답(2026-10-14 05시 발표, 남해동부앞바다)으로 snapshot() 저장까지."""
    import json
    from pathlib import Path
    real = json.loads((Path(__file__).parent / "fixtures" / "getSeaFcst_12B20100_202610140500.json").read_text(encoding="utf-8"))
    monkeypatch.setenv("KMA_AUTH_KEY", "test")
    monkeypatch.setattr(sf, "get_json", lambda url, params: real)
    monkeypatch.setattr(sf, "DIR", tmp_path)
    monkeypatch.setattr(sf, "log", lambda *a, **k: None)
    st, n, notes = sf.snapshot()
    df = pd.read_csv(next(tmp_path.glob("sea_fcst_*.csv")))
    assert st == "성공" and n == 14 * 8
    first = df[df["area"] == "부산"].iloc[0]
    assert first["date"] == "2026-10-14" and first["ampm"] == "오전" and first["wh2"] == 1.5
    assert df[df["num_ef"] == 7].iloc[0]["date"] == "2026-10-17"
