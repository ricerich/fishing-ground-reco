"""권역 조위관측소 14곳 — 1시간 관측(dtRecent) 수집 → 하루 요약

국립해양조사원 「조위관측소 최신 관측데이터」 https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService
요청 1번 = 관측소 1곳 × 하루(min=60 → 24행). 인공지능서비스 구현 1회차의 정리 규칙(고장 0.0 · 한 시간 튐)을 그대로 쓴다.
"""
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from ..markets import areas_table
from .common import RAW, CollectError, get_json, key, load_gz, log, save_gz

URL = "https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService"
COLS = ["obsrvnDt", "wtem", "artmp", "atmpr", "wspd", "maxMmntWspd", "wndrct", "bscTdlvHgt", "slntQty"]
DIR = RAW / "khoa"


def fetch_day(code, day, force=False):
    f = DIR / f"{code}_{day:%Y%m%d}.json.gz"
    if f.exists() and not force:
        return "있음", 0
    t = time.time()
    try:
        d = get_json(URL, {"serviceKey": key(), "type": "json", "obsCode": code, "reqDate": f"{day:%Y%m%d}",
                           "pageNo": 1, "numOfRows": 300, "min": 60})
    except CollectError as e:
        log("khoa", f"{code} {day}", "실패", note=str(e))
        return "실패", 0
    rc = d.get("header", {}).get("resultCode")
    if rc not in ("00", "03"):                       # 03 = 자료 없음 → 빈 목록으로 저장(다시 묻지 않기)
        log("khoa", f"{code} {day}", "실패", note=f"결과코드 {rc}")
        return "실패", 0
    items = ((d.get("body") or {}).get("items") or {}).get("item", []) if rc == "00" else []
    items = items if isinstance(items, list) else [items]
    save_gz(f, [{k: it.get(k) for k in COLS} for it in items])
    log("khoa", f"{code} {day}", "성공", len(items), time.time() - t)
    return "성공", len(items)


def collect(start, end, codes=None, workers=3, verbose=True):
    codes = codes or list(areas_table()["station_code"])
    days = pd.date_range(start, end).date
    jobs = [(c, d) for c in codes for d in days]
    done = {"성공": 0, "있음": 0, "실패": 0}
    with ThreadPoolExecutor(workers) as ex:
        for k, ((c, d), (st, n)) in enumerate(zip(jobs, ex.map(lambda j: fetch_day(*j), jobs)), 1):
            done[st] += 1
            if verbose and (k % 100 == 0 or k == len(jobs) or st == "실패"):
                print(f"  관측 {k}/{len(jobs)}  {c} {d} {st}  누계 {done}", flush=True)
    return done


# 정상 범위 — 14곳으로 늘리자 새 고장 모양이 나왔다: 완도 기온 −47℃ · 부산 기온 −39.6℃ 세 시간 · 묵호 수온 32.3℃ 뒤 22.7℃
RANGE = {"wtem": (0.5, 31), "artmp": (-18, 40), "atmpr": (950, 1050), "slntQty": (5, 40), "wspd": (0, 60)}


def _clean(h: pd.DataFrame) -> pd.DataFrame:
    """고장 표시 0.0 · 범위 밖 → NaN, 한 시간만 튄 수온 · 하루 중앙값에서 3℃ 넘게 벗어난 수온 → NaN."""
    h = h.copy()
    for c in ("wtem", "atmpr", "slntQty"):
        h.loc[h[c] == 0, c] = np.nan
    for c, (lo, hi) in RANGE.items():
        h.loc[(h[c] < lo) | (h[c] > hi), c] = np.nan
    w = h["wtem"]
    p, n = w.shift(), w.shift(-1)
    h.loc[((w - p).abs() >= 1) & ((w - n).abs() >= 1) & ((p - n).abs() < 1), "wtem"] = np.nan
    med = h["wtem"].rolling(25, center=True, min_periods=12).median()
    h.loc[(h["wtem"] - med).abs() > 3, "wtem"] = np.nan
    return h


def hourly(code) -> pd.DataFrame:
    rows = []
    for f in sorted(DIR.glob(f"{code}_*.json.gz")):
        rows += load_gz(f)
    h = pd.DataFrame(rows, columns=COLS)
    h["time"] = pd.to_datetime(h.pop("obsrvnDt"))
    h = h.drop_duplicates("time").set_index("time").sort_index().apply(pd.to_numeric, errors="coerce")
    return _clean(h)


def build_daily() -> pd.DataFrame:
    """권역 × 하루 요약. 하루 관측이 18시간 미만이면 그날 값은 NaN (반쪽 하루로 평균 내지 않기)."""
    out = []
    for a in areas_table().itertuples():
        h = hourly(a.station_code)
        if h.empty:
            continue
        g = h.resample("D")
        d = pd.DataFrame({
            "wtem_mean": g["wtem"].mean(), "wtem_min": g["wtem"].min(), "wtem_max": g["wtem"].max(),
            "artmp_mean": g["artmp"].mean(), "atmpr_mean": g["atmpr"].mean(),
            "wspd_mean": g["wspd"].mean(), "gust_max": g["maxMmntWspd"].max(),
            "tide_range": g["bscTdlvHgt"].max() - g["bscTdlvHgt"].min(), "sal_mean": g["slntQty"].mean(),
            "hours": g["wtem"].count()})
        d.loc[d["hours"] < 18, d.columns[:-1]] = np.nan
        d.insert(0, "area", a.area); d.insert(1, "station_code", a.station_code)
        out.append(d.round(2))
    return pd.concat(out).reset_index().rename(columns={"time": "date"})
