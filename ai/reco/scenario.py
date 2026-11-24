"""시연 시나리오 — 수업에서 '자동 교체가 일어나는 장면'을 정직하게 만들기 위한 장치 (DEMO_TODAY 일 때만)

실제 자료로는 매주 재학습해도 후보가 챔피언 reco_v1 과 같은 수준이라 늘 '거절'이 나온다 (그것이 옳은 결과다).
교체 장면을 보이려면 '챔피언이 약했던 상황'이 필요하다. 그래서:

  weak_champion  바다 관측(수온 · 바람 · 계절)만 쓰는 로지스틱 reco_v0_sea 를 같은 방법(≤ 6/30 학습)으로 만들어
                 챔피언 자리에 앉힌다. 위판 흐름(어제 · 7일 평균)을 안 쓰니 약하다 — 시험 P@3 약 0.41.
                 → 이어서 재학습을 돌리면 후보가 조건 5개를 모두 통과해 '교체'된다.
                 → 끝나면 관리자 화면의 되돌리기로 reco_v1 로 돌아간다.

교체 기록(promotion_log)에는 action='scenario' 로 남아 실제 운영 기록과 섞이지 않는다.
"""
import pandas as pd

from . import config as C
from . import models as M
from . import precompute, registry
from .dataset import area_day as load_area_day
from .rank import per_group
from .trainset import TRAIN_END, VAL_END, build_trainset

V0 = "reco_v0_sea"
SEA_ONLY = ["f_wtem_mean_lag1", "f_wtem_anom_lag1", "f_gust_max_lag1", "f_doy_sin", "f_doy_cos"]


def weak_champion(actor="scenario") -> dict:
    if not C.DEMO_TODAY:
        raise RuntimeError("시연 시나리오는 DEMO_TODAY 가 있을 때만 돌린다 (운영 챔피언을 바꾸지 않도록)")
    ad = load_area_day()
    T = build_trainset(d=ad, train_end=TRAIN_END)
    lab = T[T["y"].notna()]
    fit = lab[lab["date"] <= VAL_END]
    m = M.make("logistic").fit(fit[SEA_ONLY], fit["y"])
    last = ad.loc[ad["weight_kg"] > 0, "date"].max()
    E = lab[(lab["date"] > VAL_END) & (lab["date"] <= last - pd.Timedelta(days=C.LABEL_MATURE_DAYS))]
    pg = per_group(E, pd.Series(m.predict_proba(E[SEA_ONLY])[:, 1], index=E.index))
    meta = {"name": V0, "kind": "logistic", "features": SEA_ONLY, "fit_from": str(fit["date"].min().date()),
            "fit_until": str(VAL_END.date()), "stats_until": str(TRAIN_END.date()),
            "origin": "시연 시나리오 — 바다 관측만 쓰는 약한 모델"}
    registry._cache.pop(V0, None)
    registry.save_files(V0, m, meta)
    registry.register({"version": V0, "kind": "logistic", "status": "candidate", "fit_from": fit["date"].min().date(),
                       "fit_until": VAL_END.date(), "stats_until": TRAIN_END.date(),
                       "eval_from": (VAL_END + pd.Timedelta(days=1)).date(), "eval_until": E["date"].max().date(),
                       "n_train": len(fit), "n_groups": len(pg), "p_at_3": round(pg["P"].mean(), 4),
                       "hit_at_3": round(pg["Hit"].mean(), 4), "ndcg_at_3": round(pg["NDCG"].mean(), 4),
                       "features": SEA_ONLY, "file_path": f"models/registry/{V0}",
                       "decision": "시연 시나리오: 위판 흐름 없이 바다 관측만 쓰는 약한 모델을 챔피언으로 (교체 장면 실습용)"})
    prev = registry.set_champion(V0, actor=actor, reason="시연 시나리오 — 약한 챔피언으로 바꿔 두기", action="scenario")
    precompute.run([pd.Timestamp(C.today())])
    return {"from": prev, "to": V0, "p_at_3": round(float(pg["P"].mean()), 4),
            "_summary": f"시연 시나리오: 챔피언 {prev} → {V0} (시험 P@3 {pg['P'].mean():.3f}) — 이제 재학습을 돌려 보세요"}
