// 교안용 화면 캡처 — 시연 자료(DEMO_TODAY=2026-10-15) + demo 프로필로 늘 같은 화면을 찍는다
//   node scripts/capture/capture.mjs 1        (1단계 장면만)
//   node scripts/capture/capture.mjs all
// 저장: docs/captures/<단계>/<번호>-<장면>-pc.png · -mobile.png   (PC 1440px · 휴대폰 iPhone 13)
// Playwright 가 없으면: npm i -g playwright && npx playwright install chromium
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(path.join(process.cwd(), "web/node_modules/playwright")); }
const { chromium, devices } = pw;

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const WEB = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const AI = process.env.AI_BASE_URL ?? "http://127.0.0.1:8000";
const API = process.env.API_DIRECT ?? "http://127.0.0.1:8080";
const MAIL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";

const wait = (p, ms = 600) => p.waitForTimeout(ms);
const open = async (p, url) => { await p.goto(url, { waitUntil: "networkidle" }); await wait(p); };

// 장면: [번호, 이름, 설명, 동작(page), 휴대폰도 찍나, 전체 페이지인가]
const SCENES = {
  2: phase2,
  0: [
    ["01", "status", "시스템 상태 — 네 부분이 모두 정상", (p) => open(p, `${WEB}/status`), false, false],
    ["02", "status-raw", "GET /api/health 응답 원문", async (p) => { await open(p, `${WEB}/status`); await p.click("summary"); await wait(p); }, false, true],
    ["03", "fastapi-docs", "AI 서버 /docs — 내부 API 목록", (p) => open(p, `${AI}/docs`), false, false],
  ],
  1: [
    ["01", "home", "오늘의 추천 — 방어 Top-3 와 해도", (p) => open(p, `${WEB}/?species=방어&date=2026-10-15`), true, true],
    ["02", "mackerel-excluded", "고등어 — 순위에서 뺀 권역과 이유", async (p) => {
      await open(p, `${WEB}/?species=고등어&date=2026-10-15`);
      for (const s of await p.locator("summary").all()) await s.click();
      await wait(p);
    }, false, true],
    ["03", "past-day", "지난 날(9월 16일) 삼치 — 나머지 후보 표", async (p) => {
      await open(p, `${WEB}/?species=삼치&date=2026-09-16`);
      await p.locator("summary", { hasText: "나머지 후보" }).click();
      await wait(p);
    }, false, true],
    ["04", "tomorrow", "내일 — 아직 계산되지 않은 날의 안내", async (p) => { await open(p, `${WEB}/?species=방어&date=2026-10-16`); }, false, false],
  ],
};

// 2단계는 앞 장면의 상태(가입 → 메일 → 인증 → 로그인 → 연결)가 이어지므로 '흐름' 하나로 찍는다.
// 전제: Spring 을 demo,mockoauth 프로필로, scripts/mock_oauth.py 와 Mailpit 을 띄운 상태
const PC = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: "ko-KR", timezoneId: "Asia/Seoul" };
const MOBILE = () => ({ ...devices["iPhone 13"], locale: "ko-KR", timezoneId: "Asia/Seoul" });

async function mailTo(to, kind, after) {
  for (let i = 0; i < 30; i++) {
    const r = await (await fetch(`${MAIL}/api/v1/search?query=${encodeURIComponent("to:" + to)}`)).json();
    const m = r.messages.find((x) => x.Created >= after);
    if (m) {
      const full = await (await fetch(`${MAIL}/api/v1/message/${m.ID}`)).json();
      const link = full.Text.match(new RegExp(`https?://\\S+/${kind}\\?token=[A-Za-z0-9_-]+`));
      if (link) return { id: m.ID, link: link[0] };
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`메일이 오지 않음: ${to} ${kind}`);
}

async function mockPick(p, name) {                       // 모의 제공자 동의 화면에서 계정 고르기
  await p.waitForURL(/localhost:9100/);
  await p.locator("button", { hasText: name }).click();
  await p.waitForURL(/localhost:3000/);
  await p.waitForLoadState("networkidle");
  await wait(p, 800);
}

async function phase2(browser, shot) {
  const run = Math.random().toString(36).slice(2, 6);
  await fetch("http://127.0.0.1:9100/reset-run", { method: "POST" });          // 모의 소셜 계정을 '처음 보는' 상태로
  await fetch(`${MAIL}/api/v1/messages`, { method: "DELETE" });                  // 개발용 메일함 비우기 (캡처를 깔끔하게)
  const email = `minsu.${run}@example.test`, pw = "Bada2026sea", pw2 = "Haeryu2026tide";
  const ctx = await browser.newContext(PC);
  const p = await ctx.newPage();

  await open(p, `${WEB}/login`);
  await shot(p, "01", "login", "로그인 — 이메일 · 소셜 3종 · 시연 로그인", { mobile: (m) => open(m, `${WEB}/login`) });

  await open(p, `${WEB}/signup`);
  await p.fill("#name", "김민수"); await p.fill("#email", email); await p.fill("#password", "bada");
  await shot(p, "02", "signup-weak", "가입 — 비밀번호 규칙을 바로 알려 준다");
  await p.fill("#password", pw);
  const t0 = new Date(Date.now() - 2000).toISOString();
  await p.click("button[type=submit]"); await p.waitForSelector("text=메일함을 확인해 주세요"); await wait(p);
  await shot(p, "03", "signup-sent", "가입 완료 — 인증 메일을 보냈다는 안내");

  await open(p, `${WEB}/login`);
  await p.fill("#email", email); await p.fill("#password", pw); await p.click("button[type=submit]");
  await p.waitForSelector("text=이메일 인증을 마쳐야"); await wait(p);
  await shot(p, "04", "login-unverified", "인증 전 로그인 — 막고, 메일을 다시 보낼 수 있게");

  const v = await mailTo(email, "verify", t0);
  const mp = await ctx.newPage();
  await open(mp, `${MAIL}/view/${v.id}`); await wait(mp, 1200);
  await shot(mp, "05", "mail-verify", "Mailpit — 개발용 메일함에 도착한 인증 메일");
  await mp.close();

  await open(p, v.link.replace(/^https?:\/\/[^/]+/, WEB));
  await p.waitForSelector("text=로그인하러 가기");
  await shot(p, "06", "verify-ok", "메일의 버튼 → 이메일 확인 완료");

  await open(p, `${WEB}/login`);
  await p.fill("#email", email); await p.fill("#password", pw); await p.click("button[type=submit]");
  await p.waitForURL(`${WEB}/`); await p.waitForLoadState("networkidle"); await wait(p);
  await open(p, `${WEB}/me`);
  await shot(p, "07", "mypage", "마이페이지 — 로그인 수단 · 관심 목록 · 비밀번호", { full: true });

  await p.locator("li", { hasText: "네이버" }).locator("a", { hasText: "연결" }).click();
  await p.waitForURL(/localhost:9100/); await wait(p);
  await shot(p, "08", "mock-consent", "연결 — (모의) 네이버 로그인 · 동의 화면");
  await mockPick(p, "김선장");
  await shot(p, "09", "linked", "네이버 연결 완료 — 로그인 수단 2개");

  // 다른 사람이 먼저 카카오로 가입해 둔 계정을 연결하려 하면 → 거절
  const other = await browser.newContext(PC);
  const o = await other.newPage();
  await open(o, `${WEB}/login`);
  await o.locator("a", { hasText: "카카오로 계속하기" }).click();
  await mockPick(o, "항구지기");
  await shot(o, "10", "kakao-welcome", "카카오로 처음 로그인 — 새 회원 · 연결 안내");
  await other.close();
  await p.locator("li", { hasText: "카카오" }).locator("a", { hasText: "연결" }).click();
  await mockPick(p, "항구지기");
  await shot(p, "11", "link-taken", "이미 다른 회원에 붙은 카카오 → 연결 거절, 로그인은 그대로");

  await open(p, `${WEB}/me`);
  for (const t of ["삼치", "통영·거제", "여수·고흥"]) await p.locator("button[aria-pressed]", { hasText: t }).first().click();
  await p.click("text=관심 목록 저장"); await p.waitForSelector("text=저장했습니다");
  await p.locator("section", { hasText: "관심 품목" }).scrollIntoViewIfNeeded();
  await shot(p, "12", "favorites", "관심 품목 · 권역 저장");
  await open(p, `${WEB}/?date=2026-10-15`);
  await shot(p, "13", "home-favorite", "첫 화면 — 관심 품목(삼치)이 먼저, 관심 권역 표시", { full: true });

  // 비밀번호 재설정 — 새 창(로그아웃 상태)에서
  const anon = await browser.newContext(PC);
  const a = await anon.newPage();
  await open(a, `${WEB}/forgot`);
  await a.fill("#email", email);
  const t1 = new Date(Date.now() - 2000).toISOString();
  await a.click("button[type=submit]"); await a.waitForSelector("text=재설정 링크를 보냈습니다"); await wait(a);
  await shot(a, "14", "forgot-sent", "비밀번호 찾기 — 가입 여부를 드러내지 않는 같은 안내");
  const r = await mailTo(email, "reset", t1);
  await open(a, `${MAIL}/view/${r.id}`); await wait(a, 1200);
  await shot(a, "15", "mail-reset", "Mailpit — 재설정 메일(30분 · 1회용)");
  await open(a, r.link.replace(/^https?:\/\/[^/]+/, WEB));
  await a.fill("#password", pw2); await a.fill("#again", pw2);
  await shot(a, "16", "reset-form", "새 비밀번호 정하기");
  await a.click("button[type=submit]"); await a.waitForURL(/\/login\?reset=1/); await wait(a);
  await shot(a, "17", "login-after-reset", "재설정 뒤 로그인 화면 안내");
  await open(p, `${WEB}/me`); await wait(p, 1200);
  await shot(p, "18", "other-device-out", "먼저 로그인해 둔 기기 → 재설정 순간 로그인이 끊겨 로그인 화면으로");

  for (let i = 0; i < 5; i++) {
    await a.fill("#email", email); await a.fill("#password", "Wrong1234"); await a.click("button[type=submit]");
    await wait(a, 400);
  }
  await a.fill("#password", pw2); await a.click("button[type=submit]");
  await a.waitForSelector("text=잠시 잠겼습니다"); await wait(a);
  await shot(a, "19", "locked", "5번 틀리면 10분 잠금 — 재설정 링크 안내");
  await anon.close();

  const u = await browser.newContext(PC);
  const up = await u.newPage();
  await open(up, `${WEB}/login`); await up.click("text=시연 사용자"); await up.waitForURL(`${WEB}/`);
  await open(up, `${WEB}/admin`);
  await shot(up, "20", "admin-forbidden", "일반 회원이 관리자 화면 → 403 안내");
  await u.close();
  const ad = await browser.newContext(PC);
  const ap = await ad.newPage();
  await open(ap, `${WEB}/login`); await ap.click("text=시연 관리자"); await ap.waitForURL(`${WEB}/`);
  await open(ap, `${WEB}/admin`);
  await shot(ap, "21", "admin-ok", "관리자(ADMIN_EMAILS · 시연 관리자) — 머리글에 ‘관리자’ 메뉴", {
    mobile: async (m) => { await open(m, `${WEB}/login`); await m.click("text=시연 관리자"); await m.waitForURL(`${WEB}/`); await open(m, `${WEB}/me`); },
  });
  await ad.close();
  await ctx.close();
}

const only = process.argv[2] ?? "all";
const phases = only === "all" ? Object.keys(SCENES) : [only];
const browser = await chromium.launch();
const made = [];
for (const ph of phases) {
  const dir = path.join(ROOT, "docs/captures", `phase${ph}`);
  mkdirSync(dir, { recursive: true });
  if (typeof SCENES[ph] === "function") {
    const shot = async (page, no, name, desc, o = {}) => {
      const file = path.join(dir, `${no}-${name}-pc.png`);
      await page.screenshot({ path: file, fullPage: o.full ?? false });
      made.push(`${path.relative(ROOT, file)}  ${desc}`);
      if (o.mobile) {
        const mc = await browser.newContext(MOBILE());
        const m = await mc.newPage();
        await o.mobile(m);
        const mf = path.join(dir, `${no}-${name}-mobile.png`);
        await m.screenshot({ path: mf, fullPage: true });
        made.push(`${path.relative(ROOT, mf)}  ${desc} (휴대폰)`);
        await mc.close();
      }
    };
    await SCENES[ph](browser, shot);
    continue;
  }
  for (const [no, name, desc, act, mobile, full] of SCENES[ph] ?? []) {
    const targets = [["pc", { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: "ko-KR", timezoneId: "Asia/Seoul" }]];
    if (mobile) targets.push(["mobile", { ...devices["iPhone 13"], locale: "ko-KR", timezoneId: "Asia/Seoul" }]);
    for (const [kind, ctxOpts] of targets) {
      const ctx = await browser.newContext(ctxOpts);
      const page = await ctx.newPage();
      await act(page);
      const file = path.join(dir, `${no}-${name}-${kind}.png`);
      await page.screenshot({ path: file, fullPage: full });
      made.push(`${path.relative(ROOT, file)}  ${desc}`);
      await ctx.close();
    }
  }
}
await browser.close();
console.log(made.join("\n"));
