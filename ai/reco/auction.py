"""위판(위탁판매) 자료 읽기 · 하루 집계 — 모든 값이 문자열로 오므로 숫자로 바꾸는 것부터"""
import pandas as pd

from . import config as C

NUM = ["csmtQy", "csmtWt", "csmtUntpc", "csmtAmount"]


def load_day(path=None) -> pd.DataFrame:
    """하루치 원본(건별). csmtWt = 중량(kg), csmtAmount = 금액(원)."""
    df = pd.read_csv(path or C.AUCTION_DAY_CSV, dtype=str, encoding="utf-8")
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["csmtDe"], format="%Y%m%d")
    df["market"] = df["mxtrNm"].str.replace("수산업협동조합", "수협") + " " + df["csmtmktNm"]
    return df


def daily(df: pd.DataFrame) -> pd.DataFrame:
    """건별 → 날짜 × 위판장 × 품목 한 줄 (중량 · 금액 · 건수)."""
    return (df.groupby(["date", "mxtrNm", "csmtmktNm", "market", "mprcStdCodeNm"], as_index=False)
              .agg(weight_kg=("csmtWt", "sum"), amount_won=("csmtAmount", "sum"), n=("csmtWt", "size")))


def load_daily(path=None) -> pd.DataFrame:
    df = pd.read_csv(path or C.AUCTION_DAILY_CSV, encoding="utf-8", parse_dates=["date"])
    return df
