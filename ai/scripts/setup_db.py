"""MariaDB root 비밀번호만 넣으면 — 데이터베이스 2개 · 계정 2개 · 권한 · reco 표/뷰까지 한 번에 (처음 설치용)

  python scripts/setup_db.py                    # root 비밀번호를 물어본다 (화면에 안 보임)
  python scripts/setup_db.py --socket /run/mysqld/mysqld.sock   # 리눅스 root 가 소켓 인증일 때 (비밀번호 없이)
  python scripts/setup_db.py --users-only       # DB · 계정 · 권한만 (표 · 뷰는 나중에 init_db.py)
  python scripts/setup_db.py --new-passwords    # 두 계정의 비밀번호를 새로 만들어 바꾸기
  python scripts/setup_db.py --dry-run          # 실행할 SQL 만 보여 주기 (비밀번호는 가림)

하는 일
  1. root 로 접속을 확인한다 (root 비밀번호는 어디에도 저장하지 않는다 — 이 실행 동안만 메모리에)
  2. .env 의 RECO_DB_PASSWORD · APP_DB_PASSWORD · INTERNAL_TOKEN 이 비어 있으면 강한 값을 만들어 .env 에 적는다
  3. 데이터베이스 reco · app (utf8mb4) 와 계정을 만든다
       reco_ai  @localhost · @127.0.0.1  → reco 전체          (파이썬: AI 서버 · 작업 프로세스)
       reco_api @localhost · @127.0.0.1  → app 전체 + reco 의 v_svc_* 뷰 읽기만   (Spring)
  4. reco 의 표 · 뷰(db/reco/*.sql)를 만들고 뷰 읽기 권한을 준다 (init_db.py 와 같은 일)
  5. 두 계정으로 실제로 접속해 권한을 확인한다 — reco_api 는 reco 의 표를 못 읽어야 정상

몇 번 실행해도 안전하다 (IF NOT EXISTS · 비밀번호는 .env 값으로 다시 맞춤).
"""
import argparse
import getpass
import os
import re
import secrets
import string
import sys
from pathlib import Path

import pymysql

AI = Path(__file__).resolve().parents[1]
ENV = AI.parent / ".env"
EXAMPLE = AI.parent / ".env.example"
GENERATED = {"RECO_DB_PASSWORD": 24, "APP_DB_PASSWORD": 24, "INTERNAL_TOKEN": 40}


def strong(n):
    """영문 대소문자 · 숫자 (특수문자는 JDBC URL · 셸 · .env 에서 따옴표 문제를 만들 수 있어 뺐다)"""
    abc = string.ascii_letters + string.digits
    while True:
        s = "".join(secrets.choice(abc) for _ in range(n))
        if any(c.islower() for c in s) and any(c.isupper() for c in s) and any(c.isdigit() for c in s):
            return s


def read_env():
    if not ENV.exists():
        if not EXAMPLE.exists():
            sys.exit(".env 도 .env.example 도 없습니다 — 저장소 맨 위에서 실행하는지 확인하세요")
        ENV.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print("  .env 가 없어 .env.example 을 복사했습니다")
    return ENV.read_text(encoding="utf-8")


def env_value(text, key):
    m = re.search(rf"^{key}=(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def set_env_values(text, values: dict):
    """.env 의 해당 줄만 바꾼다 (주석 · 순서 · 다른 값은 그대로). 없는 키는 맨 끝에 붙인다"""
    for k, v in values.items():
        if re.search(rf"^{k}=.*$", text, re.M):
            text = re.sub(rf"^{k}=.*$", f"{k}={v}", text, count=1, flags=re.M)
        else:
            text = text.rstrip("\n") + f"\n{k}={v}\n"
    ENV.write_text(text, encoding="utf-8")


def mask(s):
    return s[:2] + "…" + f"({len(s)}자)" if s else "(비어 있음)"


def main():
    ap = argparse.ArgumentParser(description="MariaDB 데이터베이스 · 계정 만들기")
    ap.add_argument("--host", default=None, help="기본 .env 의 DB_HOST 또는 127.0.0.1")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--root-user", default=None, help="기본 root")
    ap.add_argument("--socket", default=None, help="root 소켓 인증 (리눅스) — 주면 비밀번호를 묻지 않는다")
    ap.add_argument("--users-only", action="store_true", help="DB · 계정 · 권한만")
    ap.add_argument("--new-passwords", action="store_true", help="두 계정 비밀번호를 새로 만들어 바꾸기")
    ap.add_argument("--dry-run", action="store_true", help="실행할 SQL 만 보여 주기")
    a = ap.parse_args()

    text = read_env()
    host = a.host or env_value(text, "DB_HOST") or "127.0.0.1"
    port = a.port or int(env_value(text, "DB_PORT") or 3306)
    root_user = a.root_user or env_value(text, "DB_ROOT_USER") or "root"
    sock = a.socket or env_value(text, "DB_ROOT_SOCKET")

    # 1. root 접속 확인
    print(f"\n[1] {root_user} 로 접속 ({'소켓 ' + sock if sock else f'{host}:{port}'})")
    root_pw = ""
    if not sock:
        root_pw = os.getenv("DB_ROOT_PASSWORD") or env_value(text, "DB_ROOT_PASSWORD") or getpass.getpass(f"  MariaDB {root_user} 비밀번호: ")
    opts = {"user": root_user, "password": root_pw, "charset": "utf8mb4", "autocommit": True, "connect_timeout": 5}
    opts.update(unix_socket=sock) if sock else opts.update(host=host, port=port)
    try:
        with pymysql.connect(**opts) as c, c.cursor() as cur:
            cur.execute("SELECT VERSION()")
            ver = cur.fetchone()[0]
    except pymysql.err.OperationalError as e:
        code = e.args[0]
        hint = {1045: "비밀번호가 맞지 않습니다. (리눅스에서 root 가 소켓 인증이면 --socket /run/mysqld/mysqld.sock)",
                2003: f"{host}:{port} 에 MariaDB 가 없습니다. 서버가 켜져 있는지, 포트가 맞는지 확인하세요.",
                2002: f"소켓 {sock} 에 연결할 수 없습니다."}.get(code, str(e))
        sys.exit(f"  접속 실패 — {hint}")
    print(f"  MariaDB {ver}")
    m = re.match(r"(\d+)\.(\d+)", ver)
    if m and (int(m.group(1)), int(m.group(2))) < (10, 11):
        print("  주의: 10.11 이상을 권합니다 (개발 · 시험한 버전)")

    # 2. 계정 비밀번호 · 내부 토큰 — 비어 있으면 만들어 .env 에
    print("\n[2] .env 의 계정 비밀번호 · 내부 토큰")
    vals, made = {}, []
    for k, n in GENERATED.items():
        v = env_value(text, k)
        if not v or (a.new_passwords and k != "INTERNAL_TOKEN"):
            v = strong(n)
            made.append(k)
        vals[k] = v
        print(f"  {k:17} {mask(v)}{'  ← 새로 만듦' if k in made else ''}")
    if made and not a.dry_run:
        set_env_values(text, {k: vals[k] for k in made})
        print(f"  .env 에 적었습니다 ({ENV})")
    for k, v in vals.items():
        os.environ[k] = v                      # 아래 init_db · reco.db 가 이 값을 읽는다
    os.environ.update(DB_HOST=host, DB_PORT=str(port), DB_ROOT_USER=root_user, DB_ROOT_PASSWORD=root_pw)
    if sock:
        os.environ["DB_ROOT_SOCKET"] = sock

    sys.path.insert(0, str(AI))
    import importlib.util
    spec = importlib.util.spec_from_file_location("init_db", AI / "scripts" / "init_db.py")
    init_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(init_db)

    if a.dry_run:
        print("\n[dry-run] 실행할 SQL")
        for d in (init_db.RECO_DB, init_db.APP_DB):
            print(f"  CREATE DATABASE IF NOT EXISTS `{d}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        for h in init_db.HOSTS:
            for u, k, d in ((init_db.RECO_USER, "RECO_DB_PASSWORD", init_db.RECO_DB), (init_db.APP_USER, "APP_DB_PASSWORD", init_db.APP_DB)):
                print(f"  CREATE USER IF NOT EXISTS '{u}'@'{h}' IDENTIFIED BY '{mask(vals[k])}';")
                print(f"  GRANT ALL PRIVILEGES ON `{d}`.* TO '{u}'@'{h}';")
            print(f"  GRANT SELECT ON `{init_db.RECO_DB}`.`v_svc_*` TO '{init_db.APP_USER}'@'{h}';   -- 뷰 {len(init_db.SVC_VIEWS)}개 하나씩")
        return

    # 3 · 4. DB · 계정 · 표/뷰 · 뷰 권한
    print("\n[3] 데이터베이스 · 계정 · 권한")
    init_db.create_dbs_and_users()
    if not a.users_only:
        print("\n[4] reco 표 · 뷰")
        init_db.run_reco_sql()
        init_db.grant_views()

    # 5. 두 계정으로 확인
    print("\n[5] 계정으로 접속해 확인")
    ok = True
    for user, k, own, other in ((init_db.RECO_USER, "RECO_DB_PASSWORD", init_db.RECO_DB, init_db.APP_DB),
                                (init_db.APP_USER, "APP_DB_PASSWORD", init_db.APP_DB, init_db.RECO_DB)):
        try:
            with pymysql.connect(host=host, port=port, user=user, password=vals[k], charset="utf8mb4") as c, c.cursor() as cur:
                cur.execute(f"CREATE TABLE IF NOT EXISTS `{own}`.`_setup_check` (x INT)")
                cur.execute(f"DROP TABLE `{own}`.`_setup_check`")
                msg = f"  OK  {user:9} → {own} 에 표를 만들고 지울 수 있음"
                if user == init_db.APP_USER and not a.users_only:
                    cur.execute(f"SELECT COUNT(*) FROM `{other}`.`v_svc_area`")
                    msg += f" · {other}.v_svc_area 읽기 {cur.fetchone()[0]}행"
                    try:
                        cur.execute(f"SELECT 1 FROM `{other}`.`model_registry` LIMIT 1")
                        ok, msg = False, msg + f" · 경고: {other} 의 표까지 읽힘 (뷰만 읽어야 함)"
                    except pymysql.err.OperationalError:
                        msg += f" · {other} 의 표는 막힘(정상)"
                print(msg)
        except pymysql.err.MySQLError as e:
            ok = False
            print(f"  FAIL {user} — {e.args[-1]}")
    print("\n완료" + ("" if ok else " — 위 FAIL/경고를 확인하세요"))
    if not a.users_only:
        print("다음: python -m reco.jobs run bootstrap_demo   (시연 자료 · 첫 모델 · 추천 · 채점)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
