"""수집기 공통 뼈대 — 연결 재사용 · 재시도 · 이어 받기(받은 것은 파일로) · 수집 로그(JSONL)

단원 1 U1-02 의 '기간 나눠 받기 · 재시도 · 로그'를 프로젝트용으로 다시 쓴 것.
"""
import gzip
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from .. import config as C

RAW = C.DATA / "raw"
LOG = C.DATA / "collect_log.jsonl"
_local = threading.local()
_log_lock = threading.Lock()


class CollectError(RuntimeError):
    pass


def key(name="DATA_GO_KR_KEY"):
    v = os.getenv(name, "").strip()
    if not v:
        raise CollectError(f".env 에 {name} 가 없습니다")
    return v


def session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()             # 연결 재사용 — 빠르고, 끊김(Connection reset)도 줄어든다
    return _local.s


def get_json(url, params, tries=8, timeout=40):
    """JSON 을 돌려준다. 연결 오류 · JSON 아님 → 새 연결로 바꾸고 0.5초 × n 기다렸다 다시."""
    last = None
    for i in range(tries):
        try:
            r = session().get(url, params=params, timeout=timeout)
            if r.status_code in (401, 403):
                raise CollectError(f"HTTP {r.status_code} — 키 · 활용신청 확인: {r.text[:120]}")
            return r.json()
        except CollectError:
            raise
        except (requests.RequestException, ValueError) as e:
            last = e
            _local.__dict__.pop("s", None)
            time.sleep(0.5 * (i + 1))
    raise CollectError(f"{tries}번 실패: {type(last).__name__} {str(last)[:120]}")


def save_gz(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    tmp.replace(path)                              # 다 쓴 뒤에 이름 바꾸기 → 중간에 끊겨도 반쪽 파일이 남지 않는다


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def log(source, target, status, rows=0, seconds=0.0, note=""):
    rec = {"time": datetime.now().isoformat(timespec="seconds"), "source": source, "target": target,
           "status": status, "rows": rows, "seconds": round(seconds, 2), "note": note}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with _log_lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
