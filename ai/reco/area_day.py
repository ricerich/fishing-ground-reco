"""P3 — 권역 × 품목 × 날짜 표: 위판(정답의 재료) + 조위관측소 하루 요약(특성) 붙이기

핵심 규칙
- 위판이 없는 날은 행이 없다 → 날짜를 빠짐없이 펼쳐 0 으로 채운다 (그래야 '안 팔린 날'이 보인다)
- 마지막 REFRESH_DAYS(7)일은 아직 덜 채워진 위판 → recent_incomplete=True 로 표시 (학습에서 뺄 것)
"""
import pandas as pd

from . import config as C
from .auction import load_daily
from .markets import area_of, areas_table

INCOMPLETE_DAYS = 7


def load_khoa_daily(path=None) -> pd.DataFrame:
    return pd.read_csv(path or C.SAMPLE / "khoa_daily_14areas.csv", encoding="utf-8", parse_dates=["date"])


def build(auction=None, khoa=None, species=None, end=None) -> pd.DataFrame:
    species = species or C.SPECIES
    a = load_daily() if auction is None else auction
    a = a[a["mprcStdCodeNm"].isin(species)].copy()
    a["area"] = a["mxtrNm"].map(area_of)
    a = a.dropna(subset=["area"])
    end = pd.Timestamp(end) if end is not None else a["date"].max()
    days = pd.date_range(a["date"].min(), end)
    w = (a.groupby(["area", "mprcStdCodeNm", "date"])
           .agg(weight_kg=("weight_kg", "sum"), amount_won=("amount_won", "sum"), n=("n", "sum")))
    grid = pd.MultiIndex.from_product([areas_table()["area"], species, days], names=["area", "species", "date"])
    w.index = w.index.set_names(["area", "species", "date"])
    df = w.reindex(grid, fill_value=0).reset_index()
    k = load_khoa_daily() if khoa is None else khoa
    df = df.merge(k.drop(columns=["station_code"]), on=["area", "date"], how="left")
    df["weekday"] = df["date"].dt.dayofweek                  # 0 = 월 … 6 = 일
    df["recent_incomplete"] = df["date"] > end - pd.Timedelta(days=INCOMPLETE_DAYS)
    return df
