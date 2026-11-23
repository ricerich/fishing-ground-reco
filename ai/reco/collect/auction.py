"""위판 이력 수집기 — 품목 × 하루 × 페이지(100건)

해양수산부 「위판장별 위탁판매 현황」 http://apis.data.go.kr/1192000/select0040List/getselect0040List
규칙(P1): 모든 값이 문자열 · numOfRows 최대 100 · totalCount 는 header 안 · http · 품목 검색은 '포함'
"""
import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .. import config as C
from .common import RAW, CollectError, get_json, key, load_gz, log, save_gz

URL = "http://apis.data.go.kr/1192000/select0040List/getselect0040List"
KEEP = ["csmtDe", "mxtrNm", "csmtmktNm", "fshrNm", "mprcStdCodeNm", "kdfshSttusNm", "csmtQy", "csmtWt",
        "csmtUntpc", "csmtAmount", "goodsStndrdNm", "goodsUnitNm", "orgplceSeNm"]
DIR = RAW / "auction"


def page(species, day, no):
    d = get_json(URL, {"serviceKey": key(), "type": "json", "baseDt": f"{day:%Y%m%d}",
                       "mprcStdCodeNm": species, "pageNo": no, "numOfRows": 100})
    rj = d.get("responseJson", d)
    h = rj.get("header", {})
    if h and h.get("resultCode") not in (None, "00"):
        raise CollectError(f"결과코드 {h.get('resultCode')} {h.get('resultMsg')}")
    items = (rj.get("body") or {}).get("item", []) or []
    return int(h.get("totalCount") or 0), (items if isinstance(items, list) else [items])


def fetch_day(species, day, force=False):
    """하루치 모든 페이지 → data/raw/auction/{품목}_{날짜}.json.gz. 이미 있으면 건너뛴다(이어 받기).
    force=True 로 다시 받으면 건수가 늘었는지 로그에 남긴다."""
    f = DIR / f"{species}_{day:%Y%m%d}.json.gz"
    if f.exists() and not force:
        return "있음", 0
    before = load_gz(f)["total"] if f.exists() else None
    t = time.time()
    try:
        total, items = page(species, day, 1)
        for no in range(2, (total + 99) // 100 + 1):
            items += page(species, day, no)[1]
    except CollectError as e:
        log("auction", f"{species} {day}", "실패", note=str(e))
        return "실패", 0
    if len(items) != total:                        # 페이지 도중 자료가 바뀌었거나 빠짐
        log("auction", f"{species} {day}", "개수다름", len(items), time.time() - t, f"total={total}")
    save_gz(f, {"total": total, "rows": [{k: it.get(k) for k in KEEP} for it in items]})
    note = f"다시 받음 {before} → {total}건" if before is not None else ""
    log("auction", f"{species} {day}", "성공", len(items), time.time() - t, note)
    return ("늘어남" if before is not None and total > before else "성공"), len(items)


REFRESH_DAYS = 7      # 위판 자료는 며칠에 걸쳐 채워진다 (2026-10-12: 10/14 에 9,376건 → 10/15 에 33,955건)


def collect(start, end, species=None, workers=3, verbose=True, refresh_days=REFRESH_DAYS):
    """기간 수집. 받은 날은 건너뛰되, 최근 refresh_days 일은 이미 있어도 다시 받는다(늦게 등록된 자료)."""
    species = species or C.SPECIES
    days = pd.date_range(start, end).date
    cutoff = dt.date.today() - dt.timedelta(days=refresh_days)
    jobs = [(s, d, d >= cutoff) for d in days for s in species]
    done = {"성공": 0, "늘어남": 0, "있음": 0, "실패": 0}
    with ThreadPoolExecutor(workers) as ex:
        for k, ((s, d, _), (st, n)) in enumerate(zip(jobs, ex.map(lambda j: fetch_day(*j), jobs)), 1):
            done[st] += 1
            if verbose and (k % 30 == 0 or k == len(jobs) or st == "실패"):
                print(f"  위판 {k}/{len(jobs)}  {s} {d} {st} {n}건  누계 {done}", flush=True)
    return done


def build_daily(species=None) -> pd.DataFrame:
    """받은 원본 → 날짜 × 위판장 × 품목. 품목 이름이 '정확히' 같은 것만 (삼치류 · 줄삼치 빼기)."""
    species = species or C.SPECIES
    rows = []
    for f in sorted(DIR.glob("*.json.gz")):
        rows += load_gz(f)["rows"]
    df = pd.DataFrame(rows, columns=KEEP)
    df = df[df["mprcStdCodeNm"].isin(species)].copy()
    for c in ["csmtQy", "csmtWt", "csmtUntpc", "csmtAmount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["csmtDe"], format="%Y%m%d")
    return (df.groupby(["date", "mxtrNm", "csmtmktNm", "mprcStdCodeNm"], as_index=False)
              .agg(weight_kg=("csmtWt", "sum"), amount_won=("csmtAmount", "sum"), n=("csmtWt", "size")))


def yesterday():
    return dt.date.today() - dt.timedelta(days=1)
