"""P6 — 순위 평가: (품목, 날짜)마다 권역 14곳을 점수로 줄 세우고 위 k 곳을 본다.

한 묶음 = (품목, 날짜). 그날 라벨이 있는 권역만 줄 세운다(빼기 규칙으로 빠진 권역은 제외).
'좋은 날' 권역이 하나도 없는 묶음은 뺀다 — 어떤 순위도 맞힐 수 없어 모든 모델이 같은 0 을 받는다.
  Hit@k  : 위 k 곳 중 하나라도 좋은 날이면 1        (사용자가 '하나는 건졌다')
  P@k    : 위 k 곳 중 좋은 날의 비율                 (추천 3곳의 평균 품질)
  NDCG@k : 좋은 날을 위에 둘수록 높다 (1위 > 2위 > 3위) · 그날 가능한 최선으로 나눔
"""
import numpy as np
import pandas as pd


def groups(df: pd.DataFrame, min_areas=4):
    for key, g in df.groupby(["species", "date"]):
        if len(g) >= min_areas and g["y"].sum() > 0:
            yield key, g


def one_group(y_sorted: np.ndarray, k=3) -> dict:
    top = y_sorted[:k]
    disc = 1 / np.log2(np.arange(2, k + 2))[: len(top)]
    ideal = np.sort(y_sorted)[::-1][:k]
    return {"Hit": float(top.max()), "P": float(top.mean()), "NDCG": float((top * disc).sum() / (ideal * disc[: len(ideal)]).sum())}


def per_group(df: pd.DataFrame, score: pd.Series, k=3) -> pd.DataFrame:
    """묶음마다 점수 — 부트스트랩 · 품목별 비교에 쓴다. 동점은 권역 이름 순(결과가 매번 같게)."""
    rows = []
    for (sp, dt), g in groups(df):
        g = g.assign(_s=score.loc[g.index]).sort_values(["_s", "area"], ascending=[False, True])
        rows.append({"species": sp, "date": dt, "n_areas": len(g), **one_group(g["y"].to_numpy(), k)})
    return pd.DataFrame(rows)


def rank_scores(df: pd.DataFrame, score: pd.Series, k=3) -> dict:
    pg = per_group(df, score, k)
    return {f"Hit@{k}": pg["Hit"].mean(), f"P@{k}": pg["P"].mean(), f"NDCG@{k}": pg["NDCG"].mean(), "묶음": len(pg)}


def bootstrap_diff(a: pd.DataFrame, b: pd.DataFrame, col="P", n=2000, seed=0) -> tuple:
    """같은 묶음에서 a − b 의 평균 차이와 95% 구간 (묶음을 다시 뽑기). 구간이 0 을 걸치면 '차이가 있다'고 말하기 어렵다."""
    diff = (a[col].to_numpy() - b[col].to_numpy())
    rng = np.random.default_rng(seed)
    boots = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n)])
    return diff.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5)
