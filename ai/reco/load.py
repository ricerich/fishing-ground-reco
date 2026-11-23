"""P4 — CSV · 수집 원본 → MariaDB (area → market → calendar → 사실 테이블 순서: 외래키)

부록: daily · khoa 를 넘기면 그것을 넣는다 (수집 직후 raw → build_daily 결과). 안 넘기면 sample_data.
"""
import json
import math
import time

import numpy as np
import pandas as pd

from . import config as C
from .area_day import load_khoa_daily
from .auction import load_daily
from .collect.common import LOG, RAW
from .collect.sea_forecast import REG
from .db import connect, upsert
from .markets import AREAS, area_of


def _nn(v):
    """NaN → None (DB 의 NULL)"""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def load_all(verbose=True, daily=None, khoa=None):
    out = {}
    with connect() as conn:
        t = time.time()
        upsert(conn, "area", ["area_name", "station_code", "station_name", "lat", "lon", "fcst_reg_local", "fcst_reg_broad"],
               [(a[0], a[1], a[2], a[3], a[4], *REG[a[0]]) for a in AREAS], ["area_name"])
        with conn.cursor() as cur:
            cur.execute("SELECT area_name, area_id FROM area")
            aid = dict(cur.fetchall())
        out["area"] = len(aid)

        out["species"] = upsert(conn, "species", ["species", "note"], [("고등어", "회유성"), ("방어", "회유성"), ("삼치", "회유성")], ["species"])
        daily = load_daily() if daily is None else daily
        mk = daily[["mxtrNm", "csmtmktNm"]].drop_duplicates()
        out["market"] = upsert(conn, "market", ["mxtr_nm", "csmtmkt_nm", "area_id"],
                               [(r.mxtrNm, r.csmtmktNm, aid.get(area_of(r.mxtrNm))) for r in mk.itertuples()], ["mxtr_nm", "csmtmkt_nm"])
        with conn.cursor() as cur:
            cur.execute("SELECT mxtr_nm, csmtmkt_nm, market_id FROM market")
            mid = {(a, b): i for a, b, i in cur.fetchall()}

        k = load_khoa_daily() if khoa is None else khoa
        days = pd.date_range(min(daily["date"].min(), k["date"].min()), max(daily["date"].max(), k["date"].max()))
        out["calendar"] = upsert(conn, "calendar", ["d", "weekday"], [(d.date(), d.dayofweek) for d in days], ["d"])

        rows = [(mid[(r.mxtrNm, r.csmtmktNm)], r.mprcStdCodeNm, r.date.date(), float(r.weight_kg), int(r.amount_won), int(r.n))
                for r in daily.itertuples()]
        out["auction_daily"] = upsert(conn, "auction_daily", ["market_id", "species", "sale_date", "weight_kg", "amount_won", "n_rows"],
                                      rows, ["market_id", "species", "sale_date"])

        cols = ["wtem_mean", "wtem_min", "wtem_max", "artmp_mean", "atmpr_mean", "wspd_mean", "gust_max", "tide_range", "sal_mean"]
        rows = [(aid[r["area"]], r["date"].date(), *[_nn(r[c]) for c in cols], int(r["hours"])) for _, r in k.iterrows()]
        out["obs_daily"] = upsert(conn, "obs_daily", ["area_id", "obs_date", *cols, "hours"], rows, ["area_id", "obs_date"])

        rows = []
        for f in sorted((RAW / "sea_forecast").glob("sea_fcst_*.csv")):
            for r in pd.read_csv(f, encoding="utf-8").itertuples():
                rows.append((aid[r.area], pd.to_datetime(str(r.tm_fc), format="%Y%m%d%H%M"), r.date, r.ampm, r.reg_id,
                             _nn(r.wh1), _nn(r.wh2), _nn(r.ws1), _nn(r.ws2), r.wf, _nn(r.rn_yn)))
        out["sea_forecast"] = upsert(conn, "sea_forecast", ["area_id", "tm_fc", "fc_date", "ampm", "reg_id", "wh1", "wh2", "ws1", "ws2", "wf", "rn_yn"],
                                     rows, ["area_id", "tm_fc", "fc_date", "ampm"])

        fi_files = sorted((RAW / "fishing_index").glob("fishing_index_*.csv")) or [C.FISHING_INDEX_CSV]
        alat = np.array([a[3] for a in AREAS]); alon = np.array([a[4] for a in AREAS]); anames = [a[0] for a in AREAS]
        rows = []
        for f in fi_files:
            fi = pd.read_csv(f, encoding="utf-8")
            if "collected" not in fi:
                fi.insert(0, "collected", f.stem[-8:-4] + "-" + f.stem[-4:-2] + "-" + f.stem[-2:])
            for r in fi.itertuples():
                dist = (alat - r.lat) ** 2 + ((alon - r.lot) * np.cos(np.deg2rad(r.lat))) ** 2
                near = int(dist.argmin())
                area_id = aid[anames[near]] if math.sqrt(dist[near]) * 111 <= 60 else None      # 60km 넘으면 권역 없음
                rows.append((r.collected, r.seafsPstnNm, r.predcYmd, r.predcNoonSeCd, r.seafsTgfshNm, area_id, r.lat, r.lot,
                             r.tdlvHrCn, _nn(r.maxWvhgt), _nn(r.maxWspd), _nn(r.maxWtem), r.totalIndex))
        out["fishing_index"] = upsert(conn, "fishing_index", ["collected", "place", "fc_date", "noon", "target_fish", "area_id", "lat", "lon",
                                                              "tide_phase", "max_wave", "max_wspd", "max_wtem", "total_index"],
                                      rows, ["collected", "place", "fc_date", "noon", "target_fish"])

        with conn.cursor() as cur:                      # 학습용 계층 다시 채우기 (뷰 → 기본키 있는 테이블)
            cur.execute("DELETE FROM area_sales")
            cur.execute("INSERT INTO area_sales SELECT area_id, species, sale_date, weight_kg, amount_won, n_rows FROM v_area_sales")
            out["area_sales"] = cur.rowcount
        conn.commit()

        rows = []
        if LOG.exists():
            for line in open(LOG, encoding="utf-8"):
                r = json.loads(line)
                rows.append((r["time"].replace("T", " "), r["source"], r["target"][:60], r["status"], r["rows"], r["seconds"], (r["note"] or "")[:200]))
        out["collect_log"] = upsert(conn, "collect_log", ["logged", "source", "target", "status", "n_rows", "seconds", "note"],
                                    rows, ["logged", "source", "target", "status"])
        out["초"] = round(time.time() - t, 1)
    if verbose:
        for k_, v in out.items():
            print(f"  {k_:<14} {v}")
    return out
