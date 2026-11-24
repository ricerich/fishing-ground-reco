"""매일 수집 — 실습 P2 수집기 4종을 한 번에 돌리고 DB 까지 넣는다 (작업 collect_daily)

두 가지 방식
  live   : 공공 OpenAPI 를 부른다.  .env 에 DATA_GO_KR_KEY · KMA_AUTH_KEY 가 있고 DEMO_TODAY 가 비어 있을 때
           - 위판   : 최근 7일을 다시 받는다 (위판 자료는 며칠에 걸쳐 늘어난다 — '늘어남')
           - 관측   : 권역 14곳 관측소, 최근 7일 (이미 받은 날은 '있음')
           - 해상예보 · 낚시지수 : 지금 발표를 한 장씩
           → 받은 원본(data/raw) 을 날짜 표로 만들어 DB 에 upsert (실습 P4 load_all)
  replay : 시연 · 수업용. OpenAPI 를 부르지 않고 '이미 받아 둔 원본'(sample_data)을 다시 적재하면서
           출처 × 날짜마다 수집 기록을 '재생' 상태로 남긴다. 그래서 수집 화면 · 교체 조건 1(데이터 상태)이
           실제와 같은 모양으로 움직인다.  simulate_fail=30 이면 관측 대상의 30% 를 '실패'로 적는다 (조건 1 실습).

모든 시도는 collect_log 에 한 줄씩 — 성공 · 늘어남 · 있음 · 재생 · 없음 · 실패. 실패는 숨기지 않는다.
"""
import os
import random
import time

import pandas as pd

from . import config as C
from .collect.common import log


def mode() -> str:
    has_keys = bool(os.getenv("DATA_GO_KR_KEY", "").strip())
    return "live" if has_keys and not C.DEMO_TODAY else "replay"


def run(days=None, simulate_fail=0) -> dict:
    days = int(days or 7)
    return _live(days) if mode() == "live" else _replay(days, int(simulate_fail or 0))


def _live(days):
    from .collect import auction, fishing_index, khoa, sea_forecast
    from .load import load_all
    t0 = time.time()
    end = pd.Timestamp(C.today()) - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=days - 1)
    out = {"mode": "live", "from": str(start.date()), "to": str(end.date())}
    out["auction"] = auction.collect(start.date(), end.date(), verbose=False)
    out["khoa"] = khoa.collect(start.date(), end.date(), verbose=False)
    out["sea_forecast"] = sea_forecast.snapshot()[0]
    out["fishing_index"] = fishing_index.snapshot()[0]
    out["load"] = load_all(verbose=False, daily=auction.build_daily(), khoa=khoa.build_daily())
    return _finish(out, t0)


def _replay(days, simulate_fail):
    from .area_day import load_khoa_daily
    from .auction import load_daily
    from .load import load_all
    from .markets import AREAS
    t0 = time.time()
    rnd = random.Random(f"{C.today()}-{simulate_fail}")
    daily, k = load_daily(), load_khoa_daily()
    last = min(daily["date"].max(), pd.Timestamp(C.today()) - pd.Timedelta(days=1))
    span = pd.date_range(last - pd.Timedelta(days=days - 1), last)
    out = {"mode": "replay", "from": str(span[0].date()), "to": str(span[-1].date()),
           "note": "시연 모드 — OpenAPI 대신 받아 둔 원본을 다시 적재", "auction": {}, "khoa": {}}
    note = "시연: 받아 둔 원본 재생 (OpenAPI 호출 안 함)"
    for d in span:
        for sp in C.SPECIES:
            n = int(daily[(daily["date"] == d) & (daily["mprcStdCodeNm"] == sp)]["n"].sum())
            st = "재생" if n else "없음"
            log("auction", f"{sp} {d.date()}", st, n, 0.0, note if n else "그날 위판 없음")
            out["auction"][st] = out["auction"].get(st, 0) + 1
        for a in AREAS:
            hours = k[(k["date"] == d) & (k["area"] == a[0])]["hours"]
            n = int(hours.sum()) if len(hours) else 0
            if simulate_fail and rnd.random() * 100 < simulate_fail:
                st, why = "실패", "시연: 실패 흉내 — 8번 다시 시도했지만 연결 끊김 (ConnectionResetError)"
            else:
                st, why = ("재생" if n else "없음"), note if n else "관측 없음"
            log("khoa", f"{a[0]} {d.date()}", st, 0 if st == "실패" else n, 0.0, why)
            out["khoa"][st] = out["khoa"].get(st, 0) + 1
    log("sea_forecast", f"{span[-1].date()} 발표", "재생", 28 * 3, 0.0, note)
    fi = len(pd.read_csv(C.FISHING_INDEX_CSV, encoding="utf-8"))
    log("fishing_index", f"{span[-1].date()} 발표", "재생", fi, 0.0, note)
    out["sea_forecast"], out["fishing_index"] = "재생", "재생"
    out["load"] = load_all(verbose=False)
    return _finish(out, t0)


def _finish(out, t0):
    def cnt(x):
        return x if isinstance(x, dict) else {x: 1}
    tot = {}
    for s in ("auction", "khoa", "sea_forecast", "fishing_index"):
        for st, n in cnt(out[s]).items():
            tot[st] = tot.get(st, 0) + n
    ok = sum(n for st, n in tot.items() if st in OK)
    allv = sum(tot.values())
    out["counts"], out["seconds"] = tot, round(time.time() - t0, 1)
    out["_status"] = "ok" if not tot.get("실패") else "fail" if ok == 0 else "ok"
    out["_summary"] = (f"{'시연 재생' if out['mode'] == 'replay' else '수집'} {out['from']} ~ {out['to']} · "
                       f"성공 {ok}/{allv}" + (f" · 실패 {tot['실패']}" if tot.get("실패") else "") +
                       f" · 위판 {out['load'].get('auction_daily', 0):,}행 적재")
    return out


OK = ("성공", "늘어남", "있음", "재생", "없음")   # 없음 = 그날 자료가 원래 없음(휴장 등) — 실패가 아니다
