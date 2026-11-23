"""매일 수집 — 3단계에서 채운다 (실습 P2 수집기 4종을 묶어 DB 까지)."""
from . import config as C


def run(days=None):
    return {"_status": "skipped", "_summary": "3단계에서 연결 예정", "today": str(C.today())}
