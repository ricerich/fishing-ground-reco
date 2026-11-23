"""MariaDB 연결 — 데이터베이스 reco (파이썬 소유). 접속 정보는 환경 변수에서만 읽는다."""
import os
from contextlib import contextmanager
from pathlib import Path

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from . import config as C

DB = {"host": os.getenv("DB_HOST", "127.0.0.1"), "port": int(os.getenv("DB_PORT", "3306")),
      "user": os.getenv("RECO_DB_USER", "reco_ai"), "password": os.getenv("RECO_DB_PASSWORD", ""),
      "database": os.getenv("RECO_DB_NAME", "reco")}
SQL_DIR = C.ROOT.parent / "db" / "reco"
_engine = None


def connect(database=True, **override):
    opts = {**DB, **override}
    if not database:
        opts.pop("database", None)
    return pymysql.connect(**opts, charset="utf8mb4", autocommit=False, init_command="SET time_zone = '+09:00'")


@contextmanager
def cursor(dict_rows=False):
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor if dict_rows else None) as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()


def engine():
    """pandas.read_sql 용. 비밀번호에 특수문자가 있어도 되도록 URL.create 로 만든다."""
    global _engine
    if _engine is None:
        d = DB
        url = URL.create("mysql+pymysql", username=d["user"], password=d["password"], host=d["host"],
                         port=d["port"], database=d["database"], query={"charset": "utf8mb4"})
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def split_sql(text: str) -> list[str]:
    """'--' 주석을 지우고 ';' 로 나눈 문장들 (문자열 안의 ';' 는 쓰지 않는 규칙)."""
    lines = [ln.split("--", 1)[0] for ln in text.splitlines()]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def run_sql_file(path: Path, conn=None) -> int:
    stmts = split_sql(Path(path).read_text(encoding="utf-8"))
    own = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            for s in stmts:
                cur.execute(s)
        conn.commit()
    finally:
        if own:
            conn.close()
    return len(stmts)


def upsert(conn, table, cols, rows, keys):
    """INSERT … ON DUPLICATE KEY UPDATE — 다시 넣어도 중복 없이 최신 값으로 (늦게 채워진 위판)."""
    if not rows:
        return 0
    upd = ", ".join(f"{c}=VALUES({c})" for c in cols if c not in keys) or f"{cols[0]}={cols[0]}"
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        for i in range(0, len(rows), 2000):            # 2,000행씩 나눠 보내기
            cur.executemany(sql, rows[i:i + 2000])
    conn.commit()
    return len(rows)
