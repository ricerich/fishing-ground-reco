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

const only = process.argv[2] ?? "all";
const phases = only === "all" ? Object.keys(SCENES) : [only];
const browser = await chromium.launch();
const made = [];
for (const ph of phases) {
  const dir = path.join(ROOT, "docs/captures", `phase${ph}`);
  mkdirSync(dir, { recursive: true });
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
