// 화면 끝-끝(E2E) 점검 — 사용자가 하는 그대로 브라우저를 움직여 본다. 결과: 항목별 OK / FAIL, 하나라도 FAIL 이면 종료 코드 1
//   node scripts/e2e/e2e.mjs
// 전제: 네 부분 + Spring(demo 프로필) 이 떠 있고 시연 상태(bootstrap_demo). Playwright: npm i -g playwright && npx playwright install chromium
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(path.join(process.cwd(), "web/node_modules/playwright")); }
const { chromium, devices } = pw;
const WEB = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const results = [];

async function test(name, fn) {
  const t = Date.now();
  try {
    const detail = await fn();
    results.push([true, name, detail ?? "", Date.now() - t]);
  } catch (e) {
    results.push([false, name, String(e.message ?? e).split("\n")[0].slice(0, 160), Date.now() - t]);
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };

const browser = await chromium.launch();
const ctx = () => browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "ko-KR", timezoneId: "Asia/Seoul" });
async function login(p, who) {
  await p.goto(`${WEB}/login`, { waitUntil: "networkidle" });
  await p.click(`text=${who}`);
  await p.waitForURL(`${WEB}/`);
}

const anon = await (await ctx()).newPage();
await test("첫 화면 — 방어 Top-3 와 해도", async () => {
  await anon.goto(`${WEB}/?species=방어`, { waitUntil: "networkidle" });
  await anon.waitForSelector("text=평소보다 잘 잡힐 권역");
  const cards = await anon.locator("button", { hasText: "왜 이 권역인가요?" }).count();
  expect(cards === 3, `Top-3 카드 ${cards}개`);
  expect(await anon.locator("svg[aria-label*='해도'], svg[role=img]").count() >= 1, "지도 없음");
  return "카드 3 · 지도 있음";
});
await test("품목 바꾸기 — 주소와 제목이 함께", async () => {
  await anon.click("button[role=radio]:has-text('삼치')");
  await anon.waitForURL(/species=%EC%82%BC%EC%B9%98|species=삼치/);
  await anon.waitForSelector("h1:has-text('삼치')");
  return anon.url().split("?")[1];
});
await test("추천 성적 — 요약 · 주별 그림 · 날마다", async () => {
  await anon.goto(`${WEB}/record?species=방어&weeks=8`, { waitUntil: "networkidle" });
  await anon.waitForSelector("text=주별 적중률");
  const pcts = await anon.locator("section[aria-label=요약] p.num").allTextContents();
  expect(pcts.length === 3 && pcts.every((x) => /\d+%/.test(x)), pcts.join(","));
  expect(await anon.locator("ol > li").count() >= 5, "날마다 목록이 짧다");
  return pcts.join(" · ");
});
await test("로그인 전 — 설명은 회원 기능", async () => {
  await anon.goto(`${WEB}/?species=방어`, { waitUntil: "networkidle" });
  await anon.locator("button", { hasText: "왜 이 권역인가요?" }).first().click();
  await anon.waitForSelector("text=설명은 회원에게 보여 드립니다");
});

const u = await (await ctx()).newPage();
await test("시연 사용자 로그인 → 머리글에 이름", async () => {
  await login(u, "시연 사용자");
  await u.waitForSelector("header >> text=시연 사용자님");
});
await test("추천 피드백 — 누르면 남고, 새로 고쳐도 그대로", async () => {
  await u.goto(`${WEB}/?species=방어`, { waitUntil: "networkidle" });
  const btn = u.locator("[role=group][aria-label$='추천 평가']").nth(2).locator("button", { hasText: "아니에요" });
  await btn.click();
  await u.waitForFunction(() => document.querySelectorAll("[aria-pressed=true]").length > 0);
  await u.reload({ waitUntil: "networkidle" });
  const pressed = await u.locator("[role=group][aria-label$='추천 평가']").nth(2).locator("button[aria-pressed=true]").textContent({ timeout: 8000 });
  expect(pressed === "아니에요", `새로 고친 뒤 ${pressed}`);
});
await test("근거 설명 — 스트림이 끝나고 숫자 검사 통과", async () => {
  await u.locator("button", { hasText: "왜 이 권역인가요?" }).first().click();
  await u.waitForSelector("text=도움이 됐나요?", { timeout: 60000 });
  expect(await u.locator("text=숫자가 모두 근거에 있음").count() === 1, "숫자 검사 표시 없음");
  return await u.locator("section[aria-label$='추천 설명'] h2").textContent();
});
await test("물어보기 — 근거 문서로 답", async () => {
  await u.goto(`${WEB}/ask`, { waitUntil: "networkidle" });
  await u.fill("#q", "평소보다 잘 잡힌 날은 어떻게 정하나요?");
  await u.click("button[type=submit]");
  await u.waitForSelector("text=도움이 됐나요?", { timeout: 60000 });
  const ans = await u.locator("ol[aria-label=대화] > li").last().locator("p.whitespace-pre-wrap").textContent();
  expect(ans.includes("1.5"), ans.slice(0, 80));
  return ans.slice(0, 40) + "…";
});
await test("일반 회원의 관리자 화면 → 403 안내", async () => {
  await u.goto(`${WEB}/admin`, { waitUntil: "networkidle" });
  await u.waitForSelector("text=관리자만 볼 수 있는 화면입니다");
});
await test("로그아웃 → 로그인 버튼", async () => {
  await u.click("header >> text=로그아웃");
  await u.waitForSelector("header >> a:has-text('로그인')");
});

const a = await (await ctx()).newPage();
await test("관리자 — 챔피언 · 교체 조건 5개", async () => {
  await login(a, "시연 관리자");
  await a.goto(`${WEB}/admin`, { waitUntil: "networkidle" });
  await a.waitForSelector("text=지금 서비스 중인 모델");
  const champ = (await a.locator("section:has-text('지금 서비스 중인 모델') p.text-2xl").textContent()).trim();
  await a.goto(`${WEB}/admin/models?v=${champ}`, { waitUntil: "networkidle" });
  await a.waitForSelector("text=교체 조건 5개");
  return `챔피언 ${champ}`;
});
await test("관리자 — 이용 기록에 방금 질문", async () => {
  await a.goto(`${WEB}/admin/usage`, { waitUntil: "networkidle" });
  await a.waitForSelector("text=평소보다 잘 잡힌 날은 어떻게 정하나요?");
});

const m = await (await browser.newContext({ ...devices["iPhone 13"], locale: "ko-KR" })).newPage();
await test("휴대폰 — 가로로 넘치는 화면 없음", async () => {
  const bad = [];
  for (const path_ of ["/", "/record", "/login", "/signup", "/ask"]) {
    await m.goto(`${WEB}${path_}`, { waitUntil: "networkidle" });
    const [sw, w] = await m.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    if (sw > w + 1) bad.push(`${path_} ${sw}>${w}`);
  }
  expect(!bad.length, bad.join(", "));
  return "5개 화면";
});

await browser.close();
const w = Math.max(...results.map((r) => r[1].length));
for (const [ok, name, detail, ms] of results) console.log(`${ok ? "OK  " : "FAIL"}  ${name.padEnd(w)}  ${detail} (${(ms / 1000).toFixed(1)}s)`);
const bad = results.filter((r) => !r[0]).length;
console.log(`\n${results.length - bad}/${results.length} OK`);
process.exit(bad ? 1 : 0);
