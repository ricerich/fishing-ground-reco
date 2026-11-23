"""기상청 해상예보(getSeaFcst) — 권역마다 파고 · 풍속 예보를 발표 시각 이름으로 쌓는다

기상청 API허브 https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstMsgService/getSeaFcst?authKey=…
- 응답이 {"response": {"header", "body": {"items": {"item": [...]}}}} 로 감싸져 온다 (공공데이터포털 국립해양조사원과 반대)
- 하루 3번(05 · 11 · 17시) 발표, 최근 24시간 안의 최신 발표만 → 지난 예보는 지금부터 쌓아야 한다
- numEf(발효 번호)의 뜻이 발표 시각마다 다르다 → slot() 으로 '어느 날 오전/오후'인지 계산
"""
import datetime as dt
import time

import pandas as pd

from .common import RAW, CollectError, get_json, key, log

URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstMsgService/getSeaFcst"
DIR = RAW / "sea_forecast"

# 권역 → (해상국지 코드, 해상광역 코드)  · 코드표: 기상청 「해상예보구역코드」 (교안 03_API명세_확인결과)
# 국지 코드로 안 오면 광역 코드로 다시 묻는다. 목포·신안의 국지 구역은 수업용 판단 — 지도로 확인할 것
REG = {
    "부산": ("12B20103", "12B20100"),           # 부산앞바다 · 남해동부앞바다
    "통영·거제": ("12B20102", "12B20100"),       # 경남중부남해앞바다
    "삼천포·남해": ("12B20101", "12B20100"),     # 경남서부남해앞바다
    "마산·진해": ("12B20102", "12B20100"),
    "여수·고흥": ("12B10102", "12B10100"),       # 전남동부남해앞바다 · 남해서부앞바다
    "완도·강진": ("12B10101", "12B10100"),       # 전남서부남해앞바다
    "목포·신안": ("22A30105", "12A30100"),       # 전남남부서해앞바다 · 서해남부앞바다
    "제주 북·서": ("12B10302", "12B10300"),      # 제주도북부앞바다 · 제주도앞바다
    "제주 남·동": ("12B10303", "12B10300"),      # 제주도남부앞바다
    "울산·경주": ("12C10101", "12C10100"),       # 울산앞바다 · 동해남부앞바다
    "포항·영덕": ("12C10102", "12C10100"),       # 경북남부앞바다
    "후포·죽변": ("12C10103", "12C10100"),       # 경북북부앞바다
    "삼척·강릉": ("12C20101", "12C20100"),       # 강원남부앞바다 · 동해중부앞바다
    "속초·고성": ("12C20103", "12C20100"),       # 강원북부앞바다
}


def slot(tm_fc: int, num_ef: int):
    """발표시각(202610140500) + numEf → (예보 날짜, '오전'/'오후').
    05시 발표: 0=오늘 오전, 1=오늘 오후, 2=내일 오전 … / 11 · 17시 발표: 0=오늘 오후, 1=내일 오전 …"""
    t = dt.datetime.strptime(str(tm_fc), "%Y%m%d%H%M")
    base = 0 if t.hour < 11 else 1                 # 오늘 오전 = 0, 오늘 오후 = 1 (반나절 칸)
    k = base + int(num_ef)
    return (t.date() + dt.timedelta(days=k // 2)), ("오전" if k % 2 == 0 else "오후")


def fetch(reg_id):
    d = get_json(URL, {"authKey": key("KMA_AUTH_KEY"), "regId": reg_id, "dataType": "JSON", "pageNo": 1, "numOfRows": 50})
    resp = d.get("response", d)
    rc = str(resp.get("header", {}).get("resultCode"))
    if rc not in ("00", "0"):
        raise CollectError(f"결과코드 {rc} {resp.get('header', {}).get('resultMsg')}")
    items = ((resp.get("body") or {}).get("items") or {}).get("item", [])
    return items if isinstance(items, list) else [items]


def snapshot(force=False):
    """지금 최신 발표를 권역 14곳 모두 받아 data/raw/sea_forecast/sea_fcst_{발표시각}.csv 하나로."""
    t0, rows, notes = time.time(), [], []
    for area, (local, broad) in REG.items():
        used, items = local, []
        try:
            items = fetch(local)
            if not items:
                used, items = broad, fetch(broad)
        except CollectError as e:
            try:
                used, items = broad, fetch(broad)
                notes.append(f"{area}: 국지 {local} 실패 → 광역")
            except CollectError as e2:
                notes.append(f"{area}: {e2}")
                continue
        for it in items:
            day, ampm = slot(it["tmFc"], it["numEf"])
            rows.append({"area": area, "reg_id": used, "tm_fc": it["tmFc"], "num_ef": it["numEf"], "date": day, "ampm": ampm,
                         "wh1": it.get("wh1"), "wh2": it.get("wh2"), "ws1": it.get("ws1"), "ws2": it.get("ws2"),
                         "wd1": it.get("wd1"), "wd2": it.get("wd2"), "wf": it.get("wf"), "rn_yn": it.get("rnYn")})
    if not rows:
        log("sea_forecast", "전체", "실패", note=" | ".join(notes))
        return "실패", 0, notes
    df = pd.DataFrame(rows)
    tm = df["tm_fc"].max()
    DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DIR / f"sea_fcst_{tm}.csv", index=False, encoding="utf-8")
    log("sea_forecast", str(tm), "성공", len(df), time.time() - t0, " | ".join(notes))
    return "성공", len(df), notes
