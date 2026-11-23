"""RAG 경로 — 4단계에서 채운다. 지금은 health 에 '준비 안 됨'만 알린다."""


def startup(state: dict):
    state["rag"] = {"ready": False, "reason": "4단계에서 연결"}
