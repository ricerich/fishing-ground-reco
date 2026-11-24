"""모의 소셜 로그인 서버 (:9100) — 교육 · 캡처 전용. 실제 카카오 · 네이버가 아니다.

  python scripts/mock_oauth.py          (표준 라이브러리만 씀)

OAuth 2.0 인가 코드 흐름의 세 단계를 제공자와 같은 모양으로 흉내 낸다.
  1) GET  /{p}/…/authorize   사용자가 '로그인 · 동의' → redirect_uri?code=…&state=…
  2) POST /{p}/…/token       Spring 이 서버끼리 code 를 access_token 으로 바꾼다
  3) GET  /{p}/…/me          Spring 이 토큰으로 사용자 정보를 받는다 (제공자마다 모양이 다르다)

참고: Java HttpClient 는 http:// 요청에 h2c 업그레이드 헤더를 붙인다. uvicorn 은 그때 본문을 버려서
      토큰 교환이 실패하므로, 업그레이드를 무시하고 본문을 그대로 읽는 표준 http.server 로 만들었다.
"""
import html
import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

ACCOUNTS = {
    "kakao": [
        {"id": 41001, "nickname": "바다사랑", "email": "sea.lover@example.test", "verified": True},
        {"id": 41002, "nickname": "항구지기", "email": None, "verified": False},
    ],
    "naver": [
        {"id": "nv-52001", "name": "김선장", "email": "captain.kim@example.test"},
    ],
}
LABEL = {"kakao": "카카오", "naver": "네이버"}
# 계정 id 뒤에 붙는 '회차' — 서버를 켤 때마다, 또는 POST /reset-run 때마다 바뀐다.
# 그래서 캡처 · 점검을 몇 번 돌려도 '처음 보는 소셜 계정'으로 시작한다 (DB 를 지우지 않아도 된다)
RUN = {"id": uuid.uuid4().hex[:4]}
AUTHORIZE = {"/kakao/oauth/authorize": "kakao", "/naver/oauth2.0/authorize": "naver"}
TOKEN = {"/kakao/oauth/token", "/naver/oauth2.0/token"}


def page(p, redirect_uri, state):
    rows = "".join(
        f"""<form method="get" action="/{p}/approve">
  <input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">
  <input type="hidden" name="state" value="{html.escape(state)}">
  <input type="hidden" name="who" value="{a['id']}">
  <button>{html.escape(a.get('nickname') or a.get('name'))}<small>{html.escape(a.get('email') or '이메일 제공 안 함')}</small></button>
</form>""" for a in ACCOUNTS[p])
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>모의 {LABEL[p]} 로그인</title>
<style>body{{font-family:system-ui,sans-serif;background:#e9ecef;margin:0;display:grid;place-items:center;min-height:100vh}}
main{{background:#fff;border:2px dashed #6c757d;border-radius:8px;padding:28px;width:min(360px,90vw)}}
h1{{font-size:1.2rem;margin:0 0 4px}}p{{color:#495057;font-size:.9rem;margin:0 0 18px}}
button{{display:block;width:100%;text-align:left;padding:12px 14px;margin:8px 0;border:1px solid #adb5bd;border-radius:6px;background:#f8f9fa;font-size:1rem;cursor:pointer}}
button:hover{{background:#dee2e6}}small{{display:block;color:#6c757d;font-size:.8rem}}
.tag{{display:inline-block;background:#343a40;color:#fff;font-size:.75rem;padding:2px 8px;border-radius:4px;margin-bottom:12px}}</style>
<main><span class="tag">교육용 모의 서버 · 실제 {LABEL[p]} 아님</span><h1>{LABEL[p]} 계정으로 계속하기</h1>
<p>시험 계정을 고르면 ‘로그인 + 정보 제공 동의’를 한 것으로 보고 서비스로 돌아갑니다.</p>{rows}</main></html>"""


def user_info(p, a):
    if p == "kakao":
        acc = {"profile": {"nickname": a["nickname"]}}
        if a["email"]:
            acc |= {"email": a["email"], "is_email_valid": True, "is_email_verified": a["verified"]}
        return {"id": a["id"], "kakao_account": acc}
    return {"resultcode": "00", "message": "success", "response": {"id": a["id"], "name": a["name"], "email": a["email"]}}


class H(BaseHTTPRequestHandler):
    def send(self, code, body=b"", ctype="application/json; charset=utf-8", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def js(self, code, obj):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in AUTHORIZE:
            return self.send(200, page(AUTHORIZE[u.path], q["redirect_uri"], q["state"]).encode(), "text/html; charset=utf-8")
        if u.path.endswith("/approve"):
            p = u.path.split("/")[1]
            loc = f"{q['redirect_uri']}?{urlencode({'code': f'{p}:{q['who']}', 'state': q['state']})}"
            return self.send(302, headers={"Location": loc})
        if u.path in ("/kakao/v2/user/me", "/naver/v1/nid/me"):
            p = u.path.split("/")[1]
            tok = self.headers.get("Authorization", "").removeprefix("Bearer ").removeprefix("mock.")
            prov, _, ident = tok.partition(":")
            base, _, run = ident.partition("~")             # 점검 스크립트는 '41002~run' 처럼 붙여 매번 새 계정으로 쓴다
            a = next((x for x in ACCOUNTS.get(prov, []) if str(x["id"]) == base), None)
            if prov != p or not a:
                return self.js(401, {"error": "invalid_token"})
            return self.js(200, user_info(p, a | {"id": ident if run else f"{base}~{RUN['id']}"}))
        if u.path == "/health":
            return self.js(200, {"status": "ok", "mock": True})
        self.js(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/reset-run":
            RUN["id"] = uuid.uuid4().hex[:4]
            return self.js(200, {"run": RUN["id"]})
        if self.path not in TOKEN:
            return self.js(404, {"error": "not_found"})
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        f = {k: v[0] for k, v in parse_qs(raw).items()}
        if f.get("client_secret") != "mock-secret" or f.get("grant_type") != "authorization_code":
            return self.js(401, {"error": "invalid_client"})
        self.js(200, {"access_token": f"mock.{f.get('code')}", "token_type": "bearer", "expires_in": 3600})

    def log_message(self, fmt, *args):
        print("mock-oauth", fmt % args, flush=True)


if __name__ == "__main__":
    print("모의 소셜 로그인 http://localhost:9100", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 9100), H).serve_forever()
