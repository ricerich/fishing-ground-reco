"""권역 × 품목 × 날짜 표를 어디서 읽나 — DB(서비스) 또는 CSV(실습 · 테스트). 만드는 규칙은 area_day.build 하나.

DB 에서 읽어도 CSV 와 '같은 모양'의 표를 build() 에 넘긴다 → 실습 코드 · 테스트를 그대로 쓴다.
"""
import pandas as pd

from . import config as C
from .area_day import build, load_khoa_daily
from .auction import load_daily


def auction_daily(source=None) -> pd.DataFrame:
    if (source or C.DATA_SOURCE) == "csv":
        return load_daily()
    from .db import engine
    q = """SELECT a.sale_date AS date, m.mxtr_nm AS mxtrNm, m.csmtmkt_nm AS csmtmktNm, a.species AS mprcStdCodeNm,
                  a.weight_kg, a.amount_won, a.n_rows AS n
           FROM auction_daily a JOIN market m ON m.market_id = a.market_id"""
    df = pd.read_sql(q, engine(), parse_dates=["date"])
    df["weight_kg"] = df["weight_kg"].astype(float)
    df["amount_won"] = df["amount_won"].astype(float)
    return df


KHOA_COLS = ["wtem_mean", "wtem_min", "wtem_max", "artmp_mean", "atmpr_mean", "wspd_mean", "gust_max", "tide_range", "sal_mean"]


def khoa_daily(source=None) -> pd.DataFrame:
    if (source or C.DATA_SOURCE) == "csv":
        return load_khoa_daily()
    from .db import engine
    q = f"""SELECT a.area_name AS area, a.station_code, o.obs_date AS date, {', '.join('o.' + c for c in KHOA_COLS)}, o.hours
            FROM obs_daily o JOIN area a ON a.area_id = o.area_id"""
    df = pd.read_sql(q, engine(), parse_dates=["date"])
    for c in KHOA_COLS:
        df[c] = df[c].astype(float)
    return df


def last_auction_day(auction=None) -> pd.Timestamp:
    a = auction_daily() if auction is None else auction
    return a["date"].max()


def area_day(end=None, source=None) -> pd.DataFrame:
    """end 를 주면 그날까지 날짜를 펼친다(자료 끝 다음 날 = 오늘 추천의 행을 만들기 위해)."""
    a, k = auction_daily(source), khoa_daily(source)
    last = a["date"].max()
    return build(auction=a, khoa=k, end=max(pd.Timestamp(end), last) if end is not None else last)
