"""부록 — 서비스 코드의 약속: 여러 날 한 번에 계산 = 하루씩 계산, 모델이 없으면 규칙으로, 창 나누기"""
import pandas as pd

from reco import config as C
from reco.area_day import build
from reco.recommend import features_for
from reco.retrain import windows
from reco.trainset import FEATURES, add_baseline, add_features


def test_batch_features_equal_daily():
    ad = build(end=pd.Timestamp("2026-10-15"))
    batch = add_features(add_baseline(ad))
    for D in ["2026-08-03", "2026-10-15"]:
        one = features_for(D, ad).set_index(["area", "species"])[FEATURES].sort_index()
        b = batch[batch["date"] == D].set_index(["area", "species"])[FEATURES].sort_index()
        pd.testing.assert_frame_equal(one, b, check_dtype=False)


def test_windows_leave_seven_days_for_labels():
    ad = build()
    w = windows(ad, as_of="2026-10-15")
    assert w["last_day"] == pd.Timestamp("2026-10-14")
    assert w["matured_end"] == pd.Timestamp("2026-10-07")
    assert (w["matured_end"] - w["eval_from"]).days + 1 == 7 * C.EVAL_WEEKS
    assert w["fit_until"] < w["eval_from"]


def test_today_from_demo(monkeypatch):
    monkeypatch.setattr(C, "DEMO_TODAY", "2026-10-15")
    assert str(C.today()) == "2026-10-15"
