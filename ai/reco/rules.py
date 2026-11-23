"""P6 — 규칙 기준선: 모델 없이 점수를 내는 방법. 모델은 이것들을 '확실히' 이겨야 쓸 이유가 있다."""
import numpy as np
import pandas as pd


def random_score(df, seed=0):
    return pd.Series(np.random.default_rng(seed).random(len(df)), index=df.index)


RULES = {
    "무작위": random_score,
    "큰 권역 (평소 위판량)": lambda df: df["baseline"],
    "어제 좋았던 곳 (f_rel_lag1)": lambda df: df["f_rel_lag1"].fillna(0),
    "최근 7일 좋았던 곳 (f_rel_mean7)": lambda df: df["f_rel_mean7"].fillna(0),
}
