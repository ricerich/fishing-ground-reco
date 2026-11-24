"""회원 흐름 점검 — 화면 주소(:3000)를 거쳐 실제 사용자처럼 부른다. 메일은 Mailpit(:8025) API 로 읽는다.

  ai/.venv/bin/python scripts/check_auth.py          # 항목별 OK / FAIL

전제: Spring 을 demo 프로필로 실행, Mailpit 실행, .env 의 ADMIN_EMAILS 에 admin@fishreco.local
"""
import re
import sys
import time
import uuid

import requests
from urllib.parse import parse_qs, unquote, urlparse

WEB = "http://localhost:3000"
MAILPIT = "http://127.0.0.1:8025"
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(f"{'OK  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))


def client():
    s = requests.Session()
    s.get(f"{WEB}/api/meta")                                    # XSRF-TOKEN 쿠키 받기

    def call(method, path, **kw):
        h = kw.pop("headers", {})
        tok = s.cookies.get("XSRF-TOKEN")
        if tok:
            h["X-XSRF-TOKEN"] = tok
        return s.request(method, f"{WEB}{path}", headers=h, allow_redirects=False, **kw)
    s.call = call
    return s


def mail_link(to, kind, after):
    """to 에게 온 가장 최근 메일에서 /verify?token= 또는 /reset?token= 링크를 꺼낸다"""
    for _ in range(20):
        msgs = requests.get(f"{MAILPIT}/api/v1/search", params={"query": f"to:{to}"}).json()["messages"]
        msgs = [m for m in msgs if m["Created"] >= after]
        if msgs:
            body = requests.get(f"{MAILPIT}/api/v1/message/{msgs[0]['ID']}").json()["Text"]
            m = re.search(rf"/{kind}\?token=([A-Za-z0-9_-]+)", body)
            if m:
                return m.group(1)
        time.sleep(0.3)
    return None


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


tag = uuid.uuid4().hex[:6]
email, pw = f"fisher-{tag}@example.test", "Bada2026sea"

a = client()
t0 = stamp()
r = a.call("POST", "/api/auth/signup", json={"email": email, "password": "short", "name": "어부"})
check("약한 비밀번호 거절", r.status_code == 400 and r.json().get("code") == "weak_password", str(r.status_code))
r = a.call("POST", "/api/auth/signup", json={"email": email, "password": pw, "name": "김어부"})
check("가입 → 201, 인증 메일 발송", r.status_code == 201, r.text[:80])
r = a.call("POST", "/api/auth/signup", json={"email": email.upper(), "password": pw, "name": "중복"})
check("같은 이메일(대소문자만 다름) 재가입 거절", r.status_code == 409)
r = a.call("POST", "/api/auth/login", json={"email": email, "password": pw})
check("인증 전 로그인 → 403 email_unverified", r.status_code == 403 and r.json().get("code") == "email_unverified")
tok = mail_link(email, "verify", t0)
check("Mailpit 에 인증 메일 도착", tok is not None)
r = a.call("POST", "/api/auth/verify-email", json={"token": tok})
check("인증 링크 → 확인 완료", r.status_code == 200, r.json().get("message", "")[:40])
r = a.call("POST", "/api/auth/verify-email", json={"token": tok})
check("같은 링크 두 번째 → token_used", r.status_code == 400 and r.json().get("code") == "token_used")

r = a.call("POST", "/api/auth/login", json={"email": email, "password": pw})
check("로그인 → 200", r.status_code == 200 and r.json().get("role") == "USER")
me = a.call("GET", "/api/me").json()
check("내 정보: 이메일 로그인 · 비밀번호 있음", me.get("loginWith") == "email" and me.get("hasPassword") is True)
r = a.call("PUT", "/api/me/favorites", json={"species": ["방어"], "areas": ["제주 남·동", "부산"]})
check("관심 품목 · 권역 저장", r.status_code == 200 and r.json().get("favoriteSpecies") == ["방어"], str(r.status_code))
r = a.call("PUT", "/api/me/favorites", json={"species": ["참치"], "areas": []})
check("없는 품목은 거절", r.status_code == 400)
r = a.call("DELETE", "/api/me/identities/kakao")
check("연결 안 된 카카오 해제 → 404", r.status_code == 404)
r = a.call("GET", "/api/admin/ping")
check("일반 회원의 관리자 경로 → 403", r.status_code == 403, str(r.status_code))
r = a.call("GET", "/api/me/link/kakao")
check("카카오 연결 시작 → 제공자 로그인으로 이동(302)", r.status_code == 302 and "/oauth2/authorization/kakao" in r.headers.get("Location", ""),
      r.headers.get("Location", ""))

b = client()
r = b.call("POST", "/api/auth/login", json={"email": email, "password": "Wrong1234"})
check("틀린 비밀번호 → 401", r.status_code == 401)
for _ in range(4):
    b.call("POST", "/api/auth/login", json={"email": email, "password": "Wrong1234"})
r = b.call("POST", "/api/auth/login", json={"email": email, "password": pw})
check("5번 틀린 뒤엔 맞는 비밀번호도 잠김(423)", r.status_code == 423, str(r.status_code))

t1 = stamp()
r = b.call("POST", "/api/auth/password-reset/request", json={"email": "nobody@example.test"})
check("없는 이메일 재설정 요청도 같은 응답(200)", r.status_code == 200)
r = b.call("POST", "/api/auth/password-reset/request", json={"email": email})
tok = mail_link(email, "reset", t1)
check("재설정 메일 도착", r.status_code == 200 and tok is not None)
new_pw = "Haeryu2026tide"
r = b.call("POST", "/api/auth/password-reset/confirm", json={"token": tok, "password": new_pw})
check("새 비밀번호 설정", r.status_code == 200, r.text[:60])
r = a.call("GET", "/api/me")
check("다른 기기(먼저 로그인한 세션)는 끊김 → 401", r.status_code == 401, str(r.status_code))
r = b.call("POST", "/api/auth/login", json={"email": email, "password": new_pw})
check("재설정하면 잠금도 풀리고 새 비밀번호로 로그인", r.status_code == 200, str(r.status_code))
r = b.call("PUT", "/api/me/password", json={"current": new_pw, "next": pw})
check("비밀번호 변경 후에도 이 기기는 로그인 유지", r.status_code == 200 and b.call("GET", "/api/me").status_code == 200)
r = b.call("POST", "/api/auth/logout")
check("로그아웃 → 204, 이후 401", r.status_code == 204 and b.call("GET", "/api/me").status_code == 401)

adm = f"admin@fishreco.local"
c = client()
r = c.call("POST", "/api/auth/login", json={"email": adm, "password": pw})
if r.status_code == 401:                                        # 처음이면 가입 → 인증
    t2 = stamp()
    c.call("POST", "/api/auth/signup", json={"email": adm, "password": pw, "name": "관리자"})
    c.call("POST", "/api/auth/verify-email", json={"token": mail_link(adm, "verify", t2)})
    r = c.call("POST", "/api/auth/login", json={"email": adm, "password": pw})
check("ADMIN_EMAILS 의 검증된 이메일 → ADMIN", r.status_code == 200 and r.json().get("role") == "ADMIN", r.text[:60])
r = c.call("GET", "/api/admin/ping")
check("관리자는 관리자 경로 통과", r.status_code == 200, str(r.status_code))

d = client()
r = d.call("POST", "/api/auth/demo-login", json={"role": "USER"})
check("시연 로그인(demo 프로필)", r.status_code == 200 and r.json().get("name") == "시연 사용자", str(r.status_code))
r = d.call("POST", "/api/auth/signup", json={"email": email}, headers={"X-XSRF-TOKEN": "forged"})
e = requests.post(f"{WEB}/api/auth/login", json={"email": email, "password": pw})
check("CSRF 토큰 없는 POST → 403", e.status_code == 403, str(e.status_code))

# ── 소셜 로그인 · 계정 연결 (모의 제공자 :9100 이 떠 있고 Spring 이 mockoauth 프로필일 때만) ─────
def social(sess, start, who):
    """start(/oauth2/authorization/x 또는 /api/me/link/x) → 모의 동의 화면 → who 선택 → 콜백 → 최종 화면 주소"""
    r = sess.call("GET", start)
    loc = r.headers["Location"]
    if loc.startswith("/") or loc.startswith(WEB + "/oauth2"):
        loc = loc if loc.startswith("http") else WEB + loc
        loc = sess.get(loc, allow_redirects=False).headers["Location"]
    qs = parse_qs(urlparse(loc).query)
    p = "kakao" if "kakao" in loc else "naver"
    r = sess.get(f"http://localhost:9100/{p}/approve", params={"redirect_uri": qs["redirect_uri"][0], "state": qs["state"][0], "who": who},
                 allow_redirects=False)
    r = sess.get(r.headers["Location"], allow_redirects=False)      # → :3000/login/oauth2/code/p → Spring
    return r.headers.get("Location", f"status {r.status_code}")


try:
    mock = requests.get("http://localhost:9100/health", timeout=1).ok and requests.get(f"{WEB}/api/auth/providers").json()["kakao"]
except requests.RequestException:
    mock = False
if mock:
    k = client()
    loc = social(k, "/oauth2/authorization/kakao", f"41002~{tag}")
    me = k.call("GET", "/api/me").json()
    check("카카오(모의)로 처음 로그인 → 새 회원 · 환영 화면", "/me?welcome=kakao" in loc and me.get("loginWith") == "kakao", loc)
    r = k.call("DELETE", "/api/me/identities/kakao")
    check("유일한 로그인 수단은 해제 불가 → 409", r.status_code == 409)
    loc = social(k, "/oauth2/authorization/kakao", f"41002~{tag}")
    check("같은 카카오 계정 다시 로그인 → 같은 회원", k.call("GET", "/api/me").json().get("id") == me.get("id"), loc)

    m = client()
    m.call("POST", "/api/auth/login", json={"email": email, "password": pw})
    loc = social(m, "/api/me/link/naver", f"nv-52001~{tag}")
    ids = [i["provider"] for i in m.call("GET", "/api/me").json().get("identities", [])]
    check("이메일 회원이 마이페이지에서 네이버 연결", "/me?linked=naver" in loc and ids == ["email", "naver"], f"{loc} {ids}")
    loc = social(m, "/api/me/link/kakao", f"41002~{tag}")
    check("다른 회원에 붙은 카카오는 연결 거절", "/me?link_error=" in loc, unquote(loc)[:80])
    r = m.call("DELETE", "/api/me/identities/naver")
    check("네이버 연결 해제", r.status_code == 200 and [i["provider"] for i in r.json()["identities"]] == ["email"])
    n = client()
    loc = social(n, "/oauth2/authorization/naver", f"nv-52001~{tag}")
    check("해제 뒤 그 네이버로 로그인 → 별도 새 회원(자동 합치기 없음)", "/me?welcome=naver" in loc, loc)
else:
    print("SKIP 소셜 로그인 — 모의 제공자(scripts/mock_oauth.py)와 mockoauth 프로필이 필요")

ok = sum(results)
print(f"\n{ok}/{len(results)} 통과")
sys.exit(0 if ok == len(results) else 1)
