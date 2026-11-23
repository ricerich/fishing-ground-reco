"""P3 — 권역 × 품목 × 날짜 표 규칙"""
import pandas as pd

from reco.area_day import build


def test_grid_fills_zero_and_marks_recent():
    a = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-01-10"]), "mxtrNm": ["부산시수산업협동조합"] * 2,
                      "csmtmktNm": ["다대위판장"] * 2, "mprcStdCodeNm": ["고등어"] * 2,
                      "weight_kg": [100.0, 50.0], "amount_won": [1.0, 1.0], "n": [1, 1]})
    k = pd.DataFrame({"date": pd.date_range("2026-01-01", "2026-01-10"), "area": "부산", "station_code": "DT_0005", "wtem_mean": 12.0})
    d = build(auction=a, khoa=k, species=["고등어"])
    busan = d[d["area"] == "부산"].set_index("date")
    assert len(d) == 14 * 10                                  # 권역 14 × 10일
    assert busan.loc["2026-01-05", "weight_kg"] == 0          # 위판 없는 날 → 0
    assert busan.loc["2026-01-01", "wtem_mean"] == 12.0
    assert busan["recent_incomplete"].sum() == 7              # 마지막 7일
