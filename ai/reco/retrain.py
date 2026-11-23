"""재학습 · 평가 · 자동 교체 (PRD 6절)

창 나누기 (as_of = 이 작업을 돌린 날)
  L            = 위판 자료의 마지막 날
  matured_end  = L − 7일          (그 뒤는 위판이 덜 채워져 라벨이 아직 확정되지 않음)
  평가 창      = matured_end 이전 8주
  학습         = 평가 창 이전 전부   → 평가한 모델 그대로 서비스한다 (평가 뒤 다시 학습하지 않음)

교체 조건 — 다섯 개 모두 통과해야 챔피언이 바뀐다. 하나라도 실패하면 후보는 rejected + 이유.
  1 데이터 상태 : 최근 7일 수집 성공률 ≥ 95%, 학습 행 수 ≥ 직전 모델의 90%
  2 평가일 수   : 품목마다 평가 묶음(날짜) ≥ 30
  3 챔피언 대비 : 후보 − 챔피언 P@3 ≥ 0.01, 그 차이의 95% 구간 하한 > 0
  4 규칙 대비   : 후보 P@3 ≥ 규칙 P@3
  5 품목별      : 어느 품목도 챔피언보다 0.03 넘게 낮지 않음
"""
import json

import numpy as np
import pandas as pd

from . import config as C
from . import models as M
from . import registry
from .dataset import area_day as load_area_day
from .db import connect
from .rank import bootstrap_diff, per_group
from .trainset import FEATURES, TRAIN_END, build_trainset

LABEL_STATS_UNTIL = pd.Timestamp(TRAIN_END)          # 라벨 정의 고정 (P5 의 요일 보정)
KINDS = ["logistic", "gbm"]                           # MLP 는 P6 에서 이기지 못해 기본 후보에서 뺐다


def windows(ad: pd.DataFrame, as_of=None) -> dict:
    as_of = pd.Timestamp(as_of or C.today())
    L = min(ad.loc[ad["weight_kg"] > 0, "date"].max(), as_of - pd.Timedelta(days=1))
    matured_end = L - pd.Timedelta(days=C.LABEL_MATURE_DAYS)
    eval_from = matured_end - pd.Timedelta(weeks=C.EVAL_WEEKS) + pd.Timedelta(days=1)
    return {"as_of": as_of, "last_day": L, "matured_end": matured_end, "eval_from": eval_from,
            "fit_until": eval_from - pd.Timedelta(days=1)}


def trainset(ad, stats_until):
    return build_trainset(d=ad.copy(), train_end=LABEL_STATS_UNTIL, stats_until=stats_until)


def collect_health(days=7) -> dict:
    """최근 days 일 수집 성공률. 기록이 하나도 없으면(시연 자료만 쓰는 경우) 판단하지 않고 통과로 적는다."""
    with connect() as c, c.cursor() as cur:
        cur.execute("""SELECT COUNT(*), SUM(status IN ('성공','늘어남','있음')) FROM collect_log
                       WHERE logged >= NOW() - INTERVAL %s DAY""", (days,))
        n, ok = cur.fetchone()
    n, ok = int(n or 0), int(ok or 0)
    return {"n": n, "ok": ok, "rate": (ok / n) if n else None}


def evaluate(scores: pd.Series, E: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    pg = per_group(E, scores.loc[E.index])
    return pg, {"P": float(pg["P"].mean()), "Hit": float(pg["Hit"].mean()), "NDCG": float(pg["NDCG"].mean()), "groups": len(pg)}


def _score_with(version, feats):
    return registry.score(version, feats)


def run(as_of=None, kinds=None, actor="auto", dry_run=False) -> dict:
    kinds = kinds or KINDS
    ad = load_area_day()
    w = windows(ad, as_of)
    fit_until, eval_from, matured_end = w["fit_until"], w["eval_from"], w["matured_end"]

    T = trainset(ad, fit_until)
    lab = T[T["y"].notna()]
    tr = lab[lab["date"] <= fit_until]
    E = lab[(lab["date"] >= eval_from) & (lab["date"] <= matured_end)]

    champ = registry.champion()
    champ_su = registry.stats_until(champ)
    Tc = T if champ_su is None or champ_su == fit_until else trainset(ad, champ_su)
    Ec = Tc.loc[E.index]
    pg_champ, s_champ = evaluate(_score_with(champ, Ec), Ec)
    pg_rule, s_rule = evaluate(E["f_rel_lag1"].fillna(0).astype(float), E)

    # 후보 학습 → 같은 창에서 평가
    cands = []
    for kind in kinds:
        m = M.make(kind).fit(tr[FEATURES], tr["y"])
        s = pd.Series(m.predict_proba(E[FEATURES])[:, 1], index=E.index)
        pg, sc = evaluate(s, E)
        cands.append({"kind": kind, "model": m, "pg": pg, "s": sc})
    best = max(cands, key=lambda c: c["s"]["P"])

    # 교체 조건
    health = collect_health()
    prev_n = None
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT n_train FROM model_registry WHERE version=%s", (champ,))
        r = cur.fetchone()
        prev_n = r[0] if r and r[0] else None
    pg_b = best["pg"]
    mean_diff, lo, hi = bootstrap_diff(pg_b, pg_champ, n=C.BOOTSTRAP_N)
    per_sp = {}
    for sp in C.SPECIES:
        a, b, rr = pg_b[pg_b["species"] == sp], pg_champ[pg_champ["species"] == sp], pg_rule[pg_rule["species"] == sp]
        per_sp[sp] = {"p": round(float(a["P"].mean()), 4) if len(a) else None,
                      "champ": round(float(b["P"].mean()), 4) if len(b) else None,
                      "rule": round(float(rr["P"].mean()), 4) if len(rr) else None, "days": int(len(a))}
    g = []
    rate_ok = health["rate"] is None or health["rate"] >= C.COLLECT_MIN_SUCCESS
    n_ok = prev_n is None or len(tr) >= 0.9 * prev_n
    g.append({"id": 1, "name": "데이터 상태", "pass": bool(rate_ok and n_ok),
              "detail": (f"수집 성공률 {health['rate']:.0%} ({health['ok']}/{health['n']})" if health["rate"] is not None
                         else "최근 7일 수집 기록 없음(시연 자료) — 판단 생략") + f" · 학습 {len(tr):,}행" +
                        (f" (직전 {prev_n:,}행의 {len(tr) / prev_n:.0%})" if prev_n else "")})
    min_days = min(v["days"] for v in per_sp.values())
    g.append({"id": 2, "name": "평가일 수", "pass": bool(min_days >= C.PROMO_MIN_DAYS),
              "detail": " · ".join(f"{sp} {v['days']}일" for sp, v in per_sp.items()) + f" (기준 ≥ {C.PROMO_MIN_DAYS})"})
    g.append({"id": 3, "name": "챔피언 대비", "pass": bool(mean_diff >= C.PROMO_MIN_DIFF and lo > 0),
              "detail": f"차이 {mean_diff:+.3f} [95% {lo:+.3f}, {hi:+.3f}] (기준: ≥ +{C.PROMO_MIN_DIFF:.2f}, 하한 > 0)"})
    g.append({"id": 4, "name": "규칙 대비", "pass": bool(best["s"]["P"] >= s_rule["P"]),
              "detail": f"후보 {best['s']['P']:.3f} vs 규칙 {s_rule['P']:.3f}"})
    drops = {sp: (v["p"] - v["champ"]) for sp, v in per_sp.items() if v["p"] is not None and v["champ"] is not None}
    worst = min(drops.items(), key=lambda kv: kv[1]) if drops else (None, 0)
    g.append({"id": 5, "name": "품목별", "pass": bool(all(d >= -C.PROMO_MAX_SPECIES_DROP for d in drops.values())),
              "detail": f"가장 나빠진 품목 {worst[0]} {worst[1]:+.3f} (기준 ≥ −{C.PROMO_MAX_SPECIES_DROP:.2f})"})
    passed = all(x["pass"] for x in g)
    failed = [x["name"] for x in g if not x["pass"]]

    stamp = C.now().strftime("%Y%m%d-%H%M%S")
    result = {"windows": {k: str(v.date()) for k, v in w.items()}, "champion": champ,
              "champion_score": s_champ, "rule_score": s_rule, "gates": g, "passed": passed, "candidates": []}
    for c in cands:
        v = f"{c['kind']}-{stamp}"
        is_best = c is best
        decision = ("교체: 조건 5개 통과" if passed else "거절: " + ", ".join(failed) + " 조건 미달") if is_best \
            else f"거절: 같은 회차의 {best['kind']} 보다 높지 않음 ({c['s']['P']:.4f} ≤ {best['s']['P']:.4f})"
        meta = {"name": v, "kind": c["kind"], "features": FEATURES, "fit_from": str(tr["date"].min().date()),
                "fit_until": str(fit_until.date()), "stats_until": str(fit_until.date()),
                "label": {"threshold": 1.5, "window": 28, "weekday_adjust": True, "stats_until": str(LABEL_STATS_UNTIL.date())},
                "eval": {"from": str(eval_from.date()), "until": str(matured_end.date()), **c["s"]}}
        row = {"version": v, "kind": c["kind"], "status": "candidate", "fit_from": tr["date"].min().date(),
               "fit_until": fit_until.date(), "stats_until": fit_until.date(), "eval_from": eval_from.date(),
               "eval_until": matured_end.date(), "n_train": int(len(tr)), "n_groups": c["s"]["groups"],
               "p_at_3": round(c["s"]["P"], 4), "hit_at_3": round(c["s"]["Hit"], 4), "ndcg_at_3": round(c["s"]["NDCG"], 4),
               "rule_p_at_3": round(s_rule["P"], 4), "champ_version": champ, "champ_p_at_3": round(s_champ["P"], 4),
               "diff": round(c["s"]["P"] - s_champ["P"], 4), "features": FEATURES, "decision": decision[:300],
               "file_path": str(registry.path(v).relative_to(C.ROOT)) if registry.path(v).is_relative_to(C.ROOT) else str(registry.path(v))}
        if is_best:
            row.update({"diff": round(mean_diff, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4),
                        "per_species": per_sp, "gates": g})
        result["candidates"].append({"version": v, "kind": c["kind"], "p_at_3": row["p_at_3"], "best": is_best, "decision": decision})
        if dry_run:
            continue
        registry.save_files(v, c["model"], meta)
        registry.register(row)
        if is_best and passed:
            registry.set_champion(v, actor=actor, reason=decision)
        else:
            registry.reject(v, decision, actor=actor)
    result["new_champion"] = result["candidates"][[c["best"] for c in result["candidates"]].index(True)]["version"] if passed else None
    return result


def rollback(version, actor):
    """관리자 되돌리기 — 파일이 남아 있는 버전(또는 규칙)을 다시 챔피언으로."""
    model, meta = registry.load(version)
    if version != registry.RULE and model is None:
        raise ValueError(f"{version} 의 모델 파일이 없습니다")
    return registry.set_champion(version, actor=actor, reason=f"관리자 되돌리기 → {version}", action="rollback")


def summary_line(r: dict) -> str:
    best = next(c for c in r["candidates"] if c["best"])
    return (f"{best['version']} P@3 {best['p_at_3']:.3f} vs 챔피언 {r['champion']} {r['champion_score']['P']:.3f} · "
            + ("교체" if r["passed"] else "거절 — " + ", ".join(x['name'] for x in r['gates'] if not x['pass'])))


def to_json(r) -> str:
    return json.dumps(r, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
