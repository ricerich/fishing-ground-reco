"""바다낚시지수 — 오늘 받은 6일 예보를 날짜 이름으로 쌓는다 (지난 자료는 API 가 주지 않음: 결과코드 03)

국립해양조사원 https://apis.data.go.kr/1192136/fcstFishingv2/GetFcstFishingApiServicev2
- numOfRows 최대 300 (2000 → 결과코드 10) → 1,400건 = 300 × 5페이지
- gubun(갯바위/선상)이 걸러지지 않는다 → 한 번만 받는다
"""
import datetime as dt
import time

import pandas as pd

from .common import RAW, CollectError, get_json, key, log

URL = "https://apis.data.go.kr/1192136/fcstFishingv2/GetFcstFishingApiServicev2"
DIR = RAW / "fishing_index"


def snapshot(day=None, force=False):
    day = day or dt.date.today()
    f = DIR / f"fishing_index_{day:%Y%m%d}.csv"
    if f.exists() and not force:
        return "있음", 0
    t, items, no = time.time(), [], 1
    try:
        while True:
            d = get_json(URL, {"serviceKey": key(), "type": "json", "gubun": "선상", "reqDate": f"{day:%Y%m%d}",
                               "pageNo": no, "numOfRows": 300})
            rc = d.get("header", {}).get("resultCode")
            if rc != "00":
                raise CollectError(f"결과코드 {rc} {d.get('header', {}).get('resultMsg')}")
            body = d.get("body", {})
            got = (body.get("items") or {}).get("item", [])
            items += got if isinstance(got, list) else [got]
            if len(items) >= int(body.get("totalCount") or 0) or not got:
                break
            no += 1
    except CollectError as e:
        log("fishing_index", f"{day}", "실패", note=str(e))
        return "실패", 0
    df = pd.DataFrame(items)
    df.insert(0, "collected", f"{day:%Y-%m-%d}")
    DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False, encoding="utf-8")
    log("fishing_index", f"{day}", "성공", len(df), time.time() - t)
    return "성공", len(df)


def history() -> pd.DataFrame:
    """쌓인 스냅숏 전부. 같은 예보일 · 장소 · 어종 · 오전오후는 '가장 최근에 받은 것'만 (마지막 예보가 가장 정확)."""
    fs = sorted(DIR.glob("fishing_index_*.csv"))
    if not fs:
        return pd.DataFrame()
    df = pd.concat(pd.read_csv(f, encoding="utf-8") for f in fs)
    df["lead_days"] = (pd.to_datetime(df["predcYmd"]) - pd.to_datetime(df["collected"])).dt.days
    return df.sort_values("collected").drop_duplicates(["predcYmd", "seafsPstnNm", "seafsTgfshNm", "predcNoonSeCd"], keep="last")
