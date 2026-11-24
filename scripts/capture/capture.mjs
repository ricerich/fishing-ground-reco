// 교안용 화면 캡처 — 시연 자료(DEMO_TODAY=2026-10-15) + demo 프로필로 늘 같은 화면을 찍는다
//   node scripts/capture/capture.mjs 1        (1단계 장면만)
//   node scripts/capture/capture.mjs all
// 저장: docs/captures/<단계>/<번호>-<장면>-pc.png · -mobile.png   (PC 1440px · 휴대폰 iPhone 13)
// Playwright 가 없으면: npm i -g playwright && npx playwright install chromium
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
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
  3: phase3,
  4: phase4,
  5: phase5,
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

// 3단계: 관리자 — 거절 · (시연) 교체 · 되돌리기 · 수집 실패 → 조건 1 거절. 시작 전에 시연 상태를 처음으로 되돌린다
function resetDemo() {
  const py = process.env.PYTHON ?? path.join(ROOT, "ai", process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  execFileSync(py, ["-m", "reco.jobs", "run", "bootstrap_demo"], { cwd: path.join(ROOT, "ai"), stdio: "ignore" });
}

async function runJob(p, label) {                  // 버튼 → '끝남' 까지 기다림
  await p.locator("button", { hasText: label }).first().click();
  await p.locator("[role=status]", { hasText: /끝남|실패/ }).first().waitFor({ timeout: 120000 });
  await p.waitForLoadState("networkidle"); await wait(p, 800);
}

async function phase3(browser, shot) {
  resetDemo();
  const ctx = await browser.newContext({ ...PC, viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  await open(p, `${WEB}/login`); await p.click("text=시연 관리자"); await p.waitForURL(`${WEB}/`);

  await open(p, `${WEB}/admin`);
  await shot(p, "01", "overview", "관리자 개요 — 챔피언 reco_v1 · 작업 실행 · 교체 기록", {
    full: true,
    mobile: async (m) => { await open(m, `${WEB}/login`); await m.click("text=시연 관리자"); await m.waitForURL(`${WEB}/`); await open(m, `${WEB}/admin`); },
  });

  await open(p, `${WEB}/admin/collect`);
  await runJob(p, "수집 실행");
  await shot(p, "02", "collect-ok", "수집 실행 — 출처별 성공률 100% · 한 시도 한 줄", { full: true });

  await open(p, `${WEB}/admin`);
  await runJob(p, "재학습 · 교체 판단 실행");
  await p.locator("[role=status]").first().scrollIntoViewIfNeeded();
  await shot(p, "03", "retrain-reject", "재학습 → 거절 (후보 = 챔피언 수준, 조건 3 미달)");
  await open(p, `${WEB}/admin/models`);
  await shot(p, "04", "gates-reject", "거절된 후보의 교체 조건 5개 — 차이 +0.000, 95% 구간이 0 을 품는다", { full: true });

  await open(p, `${WEB}/admin`);
  await runJob(p, "시연: 약한 챔피언 실행");
  await shot(p, "05", "scenario-weak", "시연 시나리오 — 바다 관측만 쓰는 reco_v0_sea 를 챔피언으로", { full: true });
  await open(p, `${WEB}/?species=방어&date=2026-10-15`);
  await shot(p, "06", "home-weak", "약한 모델이 서비스 중인 첫 화면 — 아래 설명에 모델 이름이 그대로 보인다", { full: true });

  await open(p, `${WEB}/admin`);
  await runJob(p, "재학습 · 교체 판단 실행");
  await p.locator("[role=status]").first().scrollIntoViewIfNeeded();
  await shot(p, "07", "retrain-promote", "재학습 → 교체 (조건 5개 통과, 오늘 추천 다시 계산)");
  await open(p, `${WEB}/admin/models`);
  await shot(p, "08", "gates-promote", "교체된 후보 — 5개 모두 ✓, 차이 +0.18 [+0.13, +0.24]", { full: true });

  await open(p, `${WEB}/admin/models?v=reco_v1`);
  await runJob(p, "reco_v1 로 되돌리기");
  await shot(p, "09", "rollback", "되돌리기 — 관리자가 reco_v1 을 다시 챔피언으로 (조건을 거치지 않음, 기록에 남음)", { full: true });

  await open(p, `${WEB}/admin/collect`);
  await p.selectOption("select", "30");
  await runJob(p, "수집 실행");
  await shot(p, "10", "collect-fail", "시연: 관측 30% 실패 → 성공률이 95% 아래로", { full: true });
  await p.check("text=실패만"); await p.waitForLoadState("networkidle"); await wait(p);
  await p.locator("section", { hasText: "수집 기록" }).scrollIntoViewIfNeeded();
  await shot(p, "11", "collect-fail-log", "실패만 보기 — 무엇이 · 왜 실패했는지");

  await open(p, `${WEB}/admin`);
  await runJob(p, "재학습 · 교체 판단 실행");
  await open(p, `${WEB}/admin/models`);
  await shot(p, "12", "gates-data", "수집이 불안하면 조건 1(데이터 상태)에서 먼저 거절", { full: true });

  const runId = await p.evaluate(async () => (await (await fetch("/api/admin/jobs?job=retrain_weekly&limit=1")).json())[0].runId);
  await open(p, `${WEB}/admin/jobs?run=${runId}`);
  await shot(p, "13", "job-detail", "작업 기록 — 재학습 한 번의 창 · 점수 · 조건이 JSON 으로", { full: true });
  await ctx.close();
  resetDemo();                                       // 다음 수업을 위해 시연 상태를 처음으로
}

// 4단계: RAG — 근거 설명 · 물어보기. 질문 제한(1분 5번)이 시연 사용자 하나에 걸리므로 순서가 중요하다
async function waitAnswer(p) {
  await p.waitForFunction(() => !document.querySelector("[aria-busy=true]"), null, { timeout: 60000 });
  await wait(p, 600);
}

async function phase4(browser, shot) {
  const demoUser = async (pg) => { await open(pg, `${WEB}/login`); await pg.click("text=시연 사용자"); await pg.waitForURL(`${WEB}/`); };
  const anon = await browser.newContext(PC);
  const a = await anon.newPage();
  await open(a, `${WEB}/?species=방어&date=2026-10-15`);
  await a.locator("button", { hasText: "왜 이 권역인가요?" }).first().click(); await wait(a);
  await a.locator("section[aria-label$='추천 설명']").scrollIntoViewIfNeeded();
  await shot(a, "01", "explain-login", "로그인 전 — 설명은 회원 기능");
  await anon.close();

  const ctx = await browser.newContext({ ...PC, viewport: { width: 1440, height: 1100 } });
  const p = await ctx.newPage();
  await demoUser(p);
  await open(p, `${WEB}/?species=방어&date=2026-10-15`);
  await p.locator("button", { hasText: "왜 이 권역인가요?" }).first().click();
  await waitAnswer(p);
  await shot(p, "02", "explain", "왜 여수·고흥이 1위인가요? — 숫자는 추천 표에서 [추천], 설명은 서비스 문서에서 [번호]", {
    full: true,
    mobile: async (m) => {
      await demoUser(m); await open(m, `${WEB}/?species=방어&date=2026-10-15`);
      await m.locator("button", { hasText: "왜 이 권역인가요?" }).first().click(); await waitAnswer(m);
      await m.locator("section[aria-label$='추천 설명']").scrollIntoViewIfNeeded();
    },
  });
  for (const s of await p.locator("section[aria-label$='추천 설명'] summary").all()) await s.click();
  await wait(p);
  await p.locator("section[aria-label$='추천 설명']").scrollIntoViewIfNeeded();
  await shot(p, "03", "explain-facts", "설명에 쓴 숫자(추천 표)와 근거 문서 펼치기 · 답 검사(인용 · 숫자)");

  await open(p, `${WEB}/ask`);
  await shot(p, "04", "ask-empty", "물어보기 — 예시 질문");
  const ask = async (q) => { await p.fill("#q", q); await p.click("button[type=submit]"); await wait(p, 400); await waitAnswer(p); };
  await ask("점수가 0.5면 잡힐 확률이 50%인가요?");
  await shot(p, "05", "ask-answer", "서비스 문서에서 찾아 답하고, 인용 번호가 근거 목록과 이어진다", { full: true });
  await ask("고등어 금어기는 언제예요?");
  await p.locator("ol[aria-label=대화] > li").last().scrollIntoViewIfNeeded();
  await shot(p, "06", "ask-unknown", "근거 문서에 없으면 — ‘제공된 자료에서 찾을 수 없습니다’");
  await ask("해파리가 보이면 어떻게 해요?");
  await p.locator("ol[aria-label=대화] > li").last().locator("summary").click(); await wait(p);
  await p.locator("ol[aria-label=대화] > li").last().scrollIntoViewIfNeeded();
  await shot(p, "07", "ask-sample-doc", "수업용 예시 문서를 쓴 답 — 답과 근거 목록에 ‘수업용 예시’ 표시");
  for (let i = 0; i < 3; i++) {
    await p.fill("#q", "모델은 언제 바뀌나요?"); await p.click("button[type=submit]"); await wait(p, 300); await waitAnswer(p);
    if (await p.locator("[role=alert]", { hasText: "1분에" }).count()) break;
  }
  await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await wait(p);
  await shot(p, "08", "ask-limit", "질문 제한 — 1분에 5번 (Spring 이 429)");
  await ctx.close();
}

// 5단계: 추천 성적 · 피드백 · 이용 기록
async function phase5(browser, shot) {
  const ctx = await browser.newContext(PC);
  const p = await ctx.newPage();
  await open(p, `${WEB}/record?species=방어&weeks=8`);
  await shot(p, "01", "record", "추천 성적 — 보여 드린 추천 · 규칙 · 무작위, 주별 그림, 날마다 맞은 권역", {
    full: true, mobile: (m) => open(m, `${WEB}/record?species=방어&weeks=8`),
  });
  const svg = p.locator("figure svg").first();
  const box = await svg.boundingBox();
  await p.mouse.move(box.x + box.width * 0.42, box.y + box.height * 0.5); await wait(p, 400);
  await svg.scrollIntoViewIfNeeded();
  await shot(p, "02", "record-hover", "주별 그림에 마우스를 올리면 그 주의 세 값");
  await open(p, `${WEB}/record?species=고등어&weeks=26`);
  await shot(p, "03", "record-mackerel-26w", "고등어 · 최근 26주", { full: true });

  await open(p, `${WEB}/login`); await p.click("text=시연 사용자"); await p.waitForURL(`${WEB}/`);
  await open(p, `${WEB}/?species=방어&date=2026-10-15`);
  const g = p.locator("[role=group][aria-label$='추천 평가']");
  await g.nth(0).locator("button", { hasText: "도움이 됐어요" }).click();
  await g.nth(2).locator("button", { hasText: "아니에요" }).click(); await wait(p);
  await shot(p, "04", "feedback", "회원은 Top-3 마다 ‘도움이 됐어요 / 아니에요’ — 그때 서비스한 모델 버전과 함께 저장");
  await ctx.close();

  const ad = await browser.newContext(PC);
  const a = await ad.newPage();
  await open(a, `${WEB}/login`); await a.click("text=시연 관리자"); await a.waitForURL(`${WEB}/`);
  await open(a, `${WEB}/admin/usage`);
  await shot(a, "05", "usage", "관리자 · 이용 기록 — 답 품질(인용 · 숫자 · 모름) · 질문과 답 · 추천 피드백 · 관리자 행동", { full: true });
  await ad.close();
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
