"""처음 한 번 — 시연 자료로 서비스를 '돌아가는 상태'로 만든다 (DEMO_TODAY=2026-10-15 기준)

1. sample_data → DB (실습 P4 load_all)
2. reco_v1 = 실습 P6 과 같은 방법: 2026-06-30 까지(train + val) 로지스틱, 평년 · 요일 보정은 2026-03-31 까지
   → 시험 구간(7/1 ~ 확정된 마지막 날)에서 채점해 레지스트리에 챔피언으로 등록
3. 규칙 rule_yesterday 도 한 줄 등록 (언제나 대기 · 되돌리기로 챔피언 가능)
4. 2026-07-01 ~ 오늘 추천을 미리 계산 (챔피언 · 규칙) → 5. 확정된 날 채점
"""
import pandas as pd

from . import config as C
from . import evaluate, precompute, registry
from . import models as M
from .dataset import area_day as load_area_day
from .db import connect
from .load import load_all
from .rank import bootstrap_diff, per_group
from .trainset import FEATURES, TRAIN_END, VAL_END, build_trainset

V1 = "reco_v1"


def run(backfill_from="2026-07-01") -> dict:
    from .collect.common import LOG
    if C.DEMO_TODAY and LOG.exists():                 # 시연을 처음부터 — 지난 시연의 수집 기록(재생 · 실패 흉내)은 지운다
        LOG.unlink()
    out = {"load": load_all(verbose=False)}
    with connect() as c, c.cursor() as cur:
        for t in ("live_eval", "rec_run", "recommendation_excluded", "recommendation", "promotion_log", "model_registry",
                  "job_queue", "collect_log"):
            cur.execute(f"DELETE FROM {t}")
        c.commit()

    ad = load_area_day()
    T = build_trainset(d=ad, train_end=TRAIN_END)
    lab = T[T["y"].notna()]
    last = ad.loc[ad["weight_kg"] > 0, "date"].max()
    matured_end = last - pd.Timedelta(days=C.LABEL_MATURE_DAYS)
    fit = lab[lab["date"] <= VAL_END]
    E = lab[(lab["date"] > VAL_END) & (lab["date"] <= matured_end)]
    m = M.make("logistic").fit(fit[FEATURES], fit["y"])
    pg = per_group(E, pd.Series(m.predict_proba(E[FEATURES])[:, 1], index=E.index))
    pg_rule = per_group(E, E["f_rel_lag1"].fillna(0))
    diff, lo, hi = bootstrap_diff(pg, pg_rule, n=C.BOOTSTRAP_N)
    per_sp = {sp: {"p": round(float(pg.loc[pg.species == sp, "P"].mean()), 4),
                   "rule": round(float(pg_rule.loc[pg_rule.species == sp, "P"].mean()), 4),
                   "days": int((pg.species == sp).sum())} for sp in C.SPECIES}
    meta = {"name": V1, "kind": "logistic", "features": FEATURES, "fit_from": str(fit["date"].min().date()),
            "fit_until": str(VAL_END.date()), "stats_until": str(TRAIN_END.date()),
            "label": {"threshold": 1.5, "window": 28, "weekday_adjust": True, "stats_until": str(TRAIN_END.date())},
            "origin": "실습 U3-P6 p6_step5_select_save.py 와 같은 방법으로 다시 학습"}
    registry.save_files(V1, m, meta)
    registry.register({"version": V1, "kind": "logistic", "status": "candidate", "fit_from": fit["date"].min().date(),
                       "fit_until": VAL_END.date(), "stats_until": TRAIN_END.date(), "eval_from": (VAL_END + pd.Timedelta(days=1)).date(),
                       "eval_until": matured_end.date(), "n_train": len(fit), "n_groups": len(pg),
                       "p_at_3": round(pg["P"].mean(), 4), "hit_at_3": round(pg["Hit"].mean(), 4), "ndcg_at_3": round(pg["NDCG"].mean(), 4),
                       "rule_p_at_3": round(pg_rule["P"].mean(), 4), "champ_version": registry.RULE,
                       "champ_p_at_3": round(pg_rule["P"].mean(), 4), "diff": round(diff, 4), "ci_low": round(lo, 4),
                       "ci_high": round(hi, 4), "per_species": per_sp, "features": FEATURES, "file_path": f"models/registry/{V1}",
                       "decision": f"시작 모델 (실습 P6): 규칙 대비 {diff:+.3f} [{lo:+.3f}, {hi:+.3f}] — 같은 수준이지만 단순 · 설명 가능"})
    registry.register({"version": registry.RULE, "kind": "rule", "status": "retired", "features": ["f_rel_lag1"],
                       "n_groups": len(pg_rule), "p_at_3": round(pg_rule["P"].mean(), 4), "hit_at_3": round(pg_rule["Hit"].mean(), 4),
                       "ndcg_at_3": round(pg_rule["NDCG"].mean(), 4), "eval_from": (VAL_END + pd.Timedelta(days=1)).date(),
                       "eval_until": matured_end.date(),
                       "decision": "기준선: 어제 위판 ÷ 평소가 큰 순서. 언제나 대기 — 모델 파일 오류 때 대신 쓰고, 되돌리기로 챔피언이 될 수 있다"})
    registry.set_champion(V1, actor="bootstrap", reason="시연 시작 모델 등록", action="bootstrap")
    out["reco_v1"] = {"P@3": round(pg["P"].mean(), 4), "rule": round(pg_rule["P"].mean(), 4), "diff": [round(diff, 4), round(lo, 4), round(hi, 4)]}

    dates = list(pd.date_range(backfill_from, C.today()))
    out["precompute"] = precompute.run(dates, served_version=V1)
    out["evaluate"] = evaluate.run()
    out["_summary"] = (f"reco_v1 P@3 {out['reco_v1']['P@3']:.3f} (규칙 {out['reco_v1']['rule']:.3f}) · "
                       f"추천 {len(dates)}일 · 채점 {out['evaluate']['evaluated']}건")
    return out
