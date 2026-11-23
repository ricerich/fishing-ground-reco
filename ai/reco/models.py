"""P6 — 후보 모델 (scikit-learn). 모두 predict_proba 로 '좋은 날 확률' = 순위 점수를 낸다.

결측(관측이 빈 날)은 학습 구간 중앙값으로 채운다 — Pipeline 안에 넣어야 val · test 에서 train 값으로 채워진다(누수 막기).
"""
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def make(kind: str, seed=0):
    if kind == "logistic":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000))
    if kind == "gbm":       # 결측을 스스로 다룬다 · 눈금(log 여부)에 덜 민감
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=seed)
    if kind == "mlp":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             MLPClassifier((32, 16), max_iter=300, early_stopping=True, random_state=seed))
    raise ValueError(kind)


KINDS = ["logistic", "gbm", "mlp"]
