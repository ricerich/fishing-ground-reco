"""데이터베이스 · 계정 만들기 → reco 스키마 SQL 실행 (처음 한 번, 다시 실행해도 안전)

  python scripts/init_db.py            # 관리자 계정으로 DB 2개 · 계정 2개 만들고 reco 표 · 뷰 생성
  python scripts/init_db.py --only-sql # 계정은 그대로, reco 의 SQL 만 다시 실행

필요한 환경 변수 (.env — 값은 직접 정한다, 저장소에는 넣지 않는다)
  DB_HOST · DB_PORT
  DB_ROOT_USER · DB_ROOT_PASSWORD     관리자(만들 때만). 리눅스 소켓 인증이면 DB_ROOT_SOCKET=/run/mysqld/mysqld.sock
  RECO_DB_PASSWORD                    reco_ai  — 파이썬(작업 프로세스 · FastAPI): reco 전체
  APP_DB_PASSWORD                     reco_api — Spring: app 전체 + reco 의 v_svc_* 뷰 읽기
"""
import argparse
import os
import sys
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reco import db  # noqa: E402

RECO_DB, APP_DB = os.getenv("RECO_DB_NAME", "reco"), os.getenv("APP_DB_NAME", "app")
RECO_USER, APP_USER = os.getenv("RECO_DB_USER", "reco_ai"), os.getenv("APP_DB_USER", "reco_api")
HOSTS = ["localhost", "127.0.0.1"]
SVC_VIEWS = ["v_svc_area", "v_svc_rec", "v_svc_excluded", "v_svc_rec_run", "v_svc_live_eval", "v_svc_models",
             "v_svc_promotions", "v_svc_jobs", "v_svc_collect", "v_svc_queue"]


def need(name):
    v = os.getenv(name, "")
    if not v:
        sys.exit(f"환경 변수 {name} 가 비어 있습니다 (.env 확인)")
    return v


def root_conn():
    opts = {"user": os.getenv("DB_ROOT_USER", "root"), "password": os.getenv("DB_ROOT_PASSWORD", ""), "charset": "utf8mb4"}
    sock = os.getenv("DB_ROOT_SOCKET", "")
    if sock:
        opts["unix_socket"] = sock
    else:
        opts.update(host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "3306")))
    return pymysql.connect(**opts, autocommit=True)


def create_dbs_and_users():
    reco_pw, app_pw = need("RECO_DB_PASSWORD"), need("APP_DB_PASSWORD")
    with root_conn() as c, c.cursor() as cur:
        for name in (RECO_DB, APP_DB):
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        for h in HOSTS:
            for user, pw in ((RECO_USER, reco_pw), (APP_USER, app_pw)):
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (user, h, pw))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (user, h, pw))       # 비밀번호를 바꿨을 때도 맞춘다
            cur.execute(f"GRANT ALL PRIVILEGES ON `{RECO_DB}`.* TO %s@%s", (RECO_USER, h))
            cur.execute(f"GRANT ALL PRIVILEGES ON `{APP_DB}`.* TO %s@%s", (APP_USER, h))
        cur.execute("FLUSH PRIVILEGES")
    print(f"  데이터베이스 {RECO_DB} · {APP_DB}, 계정 {RECO_USER} · {APP_USER} 준비")


def grant_views():
    with root_conn() as c, c.cursor() as cur:
        for h in HOSTS:
            for v in SVC_VIEWS:
                cur.execute(f"GRANT SELECT ON `{RECO_DB}`.`{v}` TO %s@%s", (APP_USER, h))
        cur.execute("FLUSH PRIVILEGES")
    print(f"  {APP_USER} 에 뷰 {len(SVC_VIEWS)}개 읽기 권한")


def run_reco_sql():
    for f in sorted(db.SQL_DIR.glob("*.sql")):
        n = db.run_sql_file(f)
        print(f"  {f.name}: 문장 {n}개")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-sql", action="store_true")
    a = ap.parse_args()
    if not a.only_sql:
        create_dbs_and_users()
    run_reco_sql()
    if not a.only_sql:
        grant_views()
    print("완료")
