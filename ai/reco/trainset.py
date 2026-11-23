"""P5 — 학습셋: 라벨(평소 대비 좋은 날) + 특성(어제까지 알 수 있는 것만)

한 행 = 권역 × 품목 × 날짜 D.  질문: 'D 날, 이 권역에서 이 품목이 평소보다 잘 팔릴까?'
- 라벨은 D 날의 위판으로 만든다 (정답)
- 특성은 D−1 까지의 위판 · 관측 + D 날의 달력(요일 · 계절)만 쓴다 (누수 금지)
"""
import numpy as np
import pandas as pd

from . import config as C
from .area_day import build

KEYS = ["area", "species"]
TRAIN_END, VAL_END = pd.Timestamp("2026-03-31"), pd.Timestamp("2026-06-30")


def add_baseline(d: pd.DataFrame, window=28, min_days=5) -> pd.DataFrame:
    """평소 = '어제까지' window 일 중 팔린 날의 중앙값. 팔린 날이 min_days 보다 적으면 평소를 모른다(NaN)."""
    d = d.sort_values(KEYS + ["date"]).copy()
    sold = d["weight_kg"].where(d["weight_kg"] > 0)
    g = sold.groupby([d[k] for k in KEYS])
    d["baseline"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=min_days).median())
    d["ratio"] = d["weight_kg"] / d["baseline"]
    return d


def label(d: pd.DataFrame, threshold=1.5, weekday_factor=None) -> pd.Series:
    """좋은 날 = 오늘 위판 ≥ threshold × 평소 (× 요일 보정). 판단할 수 없는 날은 NaN:
    평소를 모름 · 최근 7일(덜 채워짐) · 일요일(쉬는 위판장이 많음) · 돌풍 14m/s 이상인데 위판 0 (못 나간 날, P3)."""
    base = d["baseline"]
    if weekday_factor is not None:
        base = base * d.set_index(KEYS + ["weekday"]).index.map(weekday_factor).fillna(1.0).values
    y = (d["weight_kg"] >= threshold * base).astype(float)
    stormy_zero = (d["weight_kg"] == 0) & (d["gust_max"] >= 14)
    y[base.isna() | d["recent_incomplete"] | (d["weekday"] == 6) | stormy_zero] = np.nan
    return y


def weekday_factors(d: pd.DataFrame, train_end=TRAIN_END) -> dict:
    """요일 보정: 학습 구간에서만 '그 요일 ratio 중앙값'을 구한다 (검증 · 시험 값을 쓰면 누수)."""
    tr = d[(d["date"] <= pd.Timestamp(train_end)) & (d["weight_kg"] > 0) & d["ratio"].notna()]
    f = tr.groupby(KEYS + ["weekday"])["ratio"].median()
    return f.to_dict()


def add_features(d: pd.DataFrame, train_end=TRAIN_END) -> pd.DataFrame:
    """특성 — 위판 · 관측은 모두 shift(1) 이상(어제까지). 달력은 D 날 것을 써도 된다(미리 아는 것)."""
    d = d.sort_values(KEYS + ["date"]).copy()
    g = d.groupby(KEYS)
    w = d["weight_kg"]
    # 평소 대비는 0 ~ 8,600배까지 퍼져 있다(중앙값 0.5 · 평균 7.9 · 상위 1% 91배) → log1p 로 눌러 쓴다: 0 → 0, 1배 → 0.69, 10배 → 2.4
    rel = np.log1p((w / d["baseline"]).replace([np.inf, -np.inf], np.nan))
    d["f_rel_lag1"] = np.log1p(g["weight_kg"].shift(1) / d["baseline"])            # log(1 + 어제 위판 ÷ 평소)
    d["f_rel_mean7"] = rel.groupby([d[k] for k in KEYS]).transform(lambda s: s.shift(1).rolling(7, min_periods=3).mean())
    d["f_sold_days7"] = (w > 0).groupby([d[k] for k in KEYS]).transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
    last_sale = d["date"].where(w > 0).groupby([d[k] for k in KEYS]).transform(lambda s: s.shift(1).ffill())
    d["f_days_since_sale"] = (d["date"] - last_sale).dt.days
    for c in ["wtem_mean", "gust_max", "wspd_mean", "tide_range", "sal_mean"]:
        d[f"f_{c}_lag1"] = g[c].shift(1)
    d["f_wtem_d3"] = g["wtem_mean"].shift(1) - g["wtem_mean"].shift(4)                # 3일 변화
    d["f_wtem_d7"] = g["wtem_mean"].shift(1) - g["wtem_mean"].shift(8)
    clim = (d[d["date"] <= pd.Timestamp(train_end)].assign(m=lambda x: x["date"].dt.month)
            .groupby(["area", "m"])["wtem_mean"].mean())                               # 평년: 학습 구간만
    d["f_wtem_anom_lag1"] = d["f_wtem_mean_lag1"] - d.set_index(["area", d["date"].dt.month]).index.map(clim).values
    doy = d["date"].dt.dayofyear
    d["f_doy_sin"], d["f_doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    d["f_weekday"] = d["weekday"]
    d["f_gust_today"] = d["gust_max"]       # ⚠ D 날 관측 — '완벽한 해상예보'를 가정할 때만 (P6 에서 따로 실험)
    return d


FEATURES = ["f_rel_lag1", "f_rel_mean7", "f_sold_days7", "f_days_since_sale", "f_wtem_mean_lag1", "f_gust_max_lag1",
            "f_wspd_mean_lag1", "f_tide_range_lag1", "f_sal_mean_lag1", "f_wtem_d3", "f_wtem_d7", "f_wtem_anom_lag1",
            "f_doy_sin", "f_doy_cos", "f_weekday"]
ORACLE = ["f_gust_today"]


def split(date):
    return np.where(date <= TRAIN_END, "train", np.where(date <= VAL_END, "val", "test"))


def build_trainset(threshold=1.5, window=28, weekday_adjust=True, d=None, train_end=TRAIN_END, stats_until=None):
    """train_end   = 라벨의 요일 보정을 계산하는 마지막 날 (부록: 라벨 정의를 고정하려고 P5 값 그대로 둔다)
    stats_until = 특성의 평년 수온을 계산하는 마지막 날 (모델마다 = 학습 마지막 날, meta.json 에 저장)
                  서비스(recommend.features_for)도 같은 값을 써야 학습과 서비스의 특성이 같다."""
    d = add_baseline(build() if d is None else d, window=window)
    wf = weekday_factors(d, train_end) if weekday_adjust else None
    d["y"] = label(d, threshold, wf)
    d = add_features(d, stats_until or train_end)
    d["split"] = split(d["date"])
    return d
