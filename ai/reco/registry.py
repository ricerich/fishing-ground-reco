"""모델 레지스트리 — 파일(models/registry/<버전>/model.joblib · meta.json) + DB 표 model_registry

- 챔피언은 언제나 하나. 규칙 'rule_yesterday' 도 한 줄로 등록돼 있고, 챔피언이 될 수도 있다.
- 모델 파일은 지우지 않는다 → 되돌리기는 상태만 바꾼다.
"""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from . import config as C
from .db import connect

RULE = "rule_yesterday"
_cache: dict[str, tuple] = {}


def path(version):
    return C.MODELS / version


def save_files(version, model, meta: dict):
    d = path(version)
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, d / "model.joblib")
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return d


def load(version):
    """(모델 또는 None, meta). 규칙이거나 파일이 없으면 모델은 None → 규칙으로 점수."""
    if version in _cache:
        return _cache[version]
    if version == RULE:
        out = (None, {"name": RULE, "kind": "rule", "features": ["f_rel_lag1"], "stats_until": None})
    else:
        d = path(version)
        try:
            out = (joblib.load(d / "model.joblib"), json.loads((d / "meta.json").read_text(encoding="utf-8")))
        except FileNotFoundError:
            return None, {"name": RULE, "kind": "rule", "features": ["f_rel_lag1"], "missing": version}
    _cache[version] = out
    return out


def score(version, feats: pd.DataFrame) -> pd.Series:
    """특성 표 → 점수(클수록 위). 규칙 = 어제 위판 ÷ 평소."""
    model, meta = load(version)
    if model is None:
        return feats["f_rel_lag1"].fillna(0).astype(float)
    return pd.Series(model.predict_proba(feats[meta["features"]])[:, 1], index=feats.index)


def contributions(version, feats: pd.DataFrame) -> pd.DataFrame:
    """'왜 이 순위인가'에 쓸 특성별 기여.
    로지스틱 = 계수 × 표준화 값(정확한 기여). 그 밖의 모델 = 오늘 후보들 사이에서 두드러진 정도(z 점수)."""
    model, meta = load(version)
    if model is None:
        return pd.DataFrame({"f_rel_lag1": feats["f_rel_lag1"].fillna(0)}, index=feats.index)
    cols = meta["features"]
    lr = getattr(model, "steps", None)
    if lr and hasattr(model[-1], "coef_"):
        z = model[1].transform(model[0].transform(feats[cols]))
        return pd.DataFrame(z * model[-1].coef_[0], columns=cols, index=feats.index)
    x = feats[cols].astype(float)
    return ((x - x.mean()) / x.std(ddof=0).replace(0, np.nan)).fillna(0)


# ── DB ─────────────────────────────────────────────────────────────

def champion() -> str:
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT version FROM model_registry WHERE status='champion' LIMIT 1")
        r = cur.fetchone()
    return r[0] if r else RULE


def stats_until(version):
    _, meta = load(version)
    v = meta.get("stats_until")
    return pd.Timestamp(v) if v else None


ROW_COLS = ["version", "kind", "status", "created_at", "fit_from", "fit_until", "stats_until", "eval_from", "eval_until",
            "n_train", "n_groups", "p_at_3", "hit_at_3", "ndcg_at_3", "rule_p_at_3", "champ_version", "champ_p_at_3",
            "diff", "ci_low", "ci_high", "per_species", "gates", "decision", "features", "file_path"]


def register(row: dict):
    row = {**row, "created_at": row.get("created_at") or C.now().replace(tzinfo=None)}
    vals = []
    for c in ROW_COLS:
        v = row.get(c)
        vals.append(json.dumps(v, ensure_ascii=False, default=float) if isinstance(v, (dict, list)) else v)
    upd = ", ".join(f"{c}=VALUES({c})" for c in ROW_COLS if c != "version")
    with connect() as c, c.cursor() as cur:
        cur.execute(f"INSERT INTO model_registry ({', '.join(ROW_COLS)}) VALUES ({', '.join(['%s'] * len(ROW_COLS))}) "
                    f"ON DUPLICATE KEY UPDATE {upd}", vals)
        c.commit()


def log_promotion(cur, action, frm, to, actor, reason):
    cur.execute("INSERT INTO promotion_log (at, action, from_version, to_version, actor, reason) VALUES (%s,%s,%s,%s,%s,%s)",
                (C.now().replace(tzinfo=None), action, frm, to, actor, (reason or "")[:300]))


def set_champion(version, actor="auto", reason="", action="promote"):
    """version 을 챔피언으로. 이전 챔피언은 retired. 한 트랜잭션."""
    now = C.now().replace(tzinfo=None)
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT version FROM model_registry WHERE status='champion' FOR UPDATE")
        prev = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM model_registry WHERE version=%s", (version,))
        if not cur.fetchone()[0]:
            raise ValueError(f"등록되지 않은 버전: {version}")
        cur.execute("UPDATE model_registry SET status='retired', retired_at=%s WHERE status='champion' AND version<>%s", (now, version))
        cur.execute("UPDATE model_registry SET status='champion', promoted_at=%s, retired_at=NULL WHERE version=%s", (now, version))
        log_promotion(cur, action, prev[0] if prev else None, version, actor, reason)
        c.commit()
    _cache.clear()
    return prev[0] if prev else None


def reject(version, reason, actor="auto"):
    with connect() as c, c.cursor() as cur:
        cur.execute("UPDATE model_registry SET status='rejected' WHERE version=%s AND status='candidate'", (version,))
        cur.execute("SELECT version FROM model_registry WHERE status='champion' LIMIT 1")
        r = cur.fetchone()
        log_promotion(cur, "reject", r[0] if r else None, version, actor, reason)
        c.commit()


def listing() -> list[dict]:
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT version, kind, status, p_at_3, decision FROM model_registry ORDER BY created_at DESC")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def new_version(kind: str) -> str:
    return f"{kind}-{datetime.now(C.TZ):%Y%m%d-%H%M%S}"
