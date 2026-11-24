"""하이브리드 검색 — BM25(낱말, Kiwi 형태소) + TF-IDF(글자 2~4개 조각) 의 순위를 RRF 로 합친다 (U2 4회차)

임베딩(e5)은 처음 실행 때 모델을 내려받아야 해서 기본에서 뺐다. 문서가 적고 낱말이 정해진 분야라 이 둘로 충분했다.
"""
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

RRF_K = 60
_kiwi = None
KEEP = ("NNG", "NNP", "NNB", "NR", "SN", "SL", "SH", "XR", "VV", "VA")

# 현장 말 → 문서 말 (질의 확장, U2 3회차)
GLOSSARY = {"뜨거운": "고수온", "따뜻": "고수온", "붉은": "적조", "쏘는": "해파리", "물 온도": "수온", "바닷물 온도": "수온",
            "바람": "풍속 돌풍", "왜": "근거", "많이 잡": "위판량 평소", "잘 잡": "좋은 날 평소", "확률": "점수",
            "모델 바뀌": "교체 조건", "언제 바뀌": "교체 조건 재학습"}


def tokens(text):
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    out = []
    for t in _kiwi.tokenize(text.lower()):
        if t.tag.split("-")[0] in KEEP or t.form == "℃":
            out.append(t.form)
    return out or ["_"]


def expand(q):
    add = sorted({v for k, v in GLOSSARY.items() if k in q})
    return f"{q} {' '.join(add)}" if add else q


class Hybrid:
    def __init__(self, chunks):
        self.chunks = chunks
        texts = [f"{c['title']} {c['section']} {c['text']}" for c in chunks]
        self.bm25 = BM25Okapi([tokens(t) for t in texts])
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self.mat = self.tfidf.fit_transform([re.sub(r"\s+", " ", t) for t in texts])

    def search(self, query, k=4, kinds=None, depth=20):
        q = expand(query)
        s_b = self.bm25.get_scores(tokens(q))
        s_t = (self.mat @ self.tfidf.transform([q]).T).toarray().ravel()
        ok = np.array([kinds is None or c["kind"] in kinds for c in self.chunks])
        fused = {}
        for s in (s_b, s_t):
            order = [i for i in np.argsort(-s) if ok[i] and s[i] > 0][:depth]
            for r, i in enumerate(order):
                fused[i] = fused.get(i, 0) + 1 / (RRF_K + r + 1)
        top = sorted(fused, key=lambda i: -fused[i])[:k]
        return [{**self.chunks[i], "score": round(fused[i], 4)} for i in top]
