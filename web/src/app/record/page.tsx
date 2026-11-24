"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { History, Species } from "@/lib/types";
import { dayLabel, pct } from "@/lib/format";
import { WeeklyChart } from "@/components/record/WeeklyChart";

const SPECIES: Species[] = ["고등어", "방어", "삼치"];
const WEEKS = [4, 8, 13, 26];

function verdict(served: number, rule: number) {
  const d = served - rule;
  if (Math.abs(d) < 0.02) return "규칙(어제 좋았던 곳)과 같은 수준입니다.";
  return d > 0 ? `규칙보다 ${pct(d)}p 높았습니다.` : `규칙보다 ${pct(-d)}p 낮았습니다.`;
}

function Record() {
  const sp = useSearchParams();
  const router = useRouter();
  const species = (SPECIES.includes(sp.get("species") as Species) ? sp.get("species") : "방어") as Species;
  const weeks = WEEKS.includes(Number(sp.get("weeks"))) ? Number(sp.get("weeks")) : 8;
  const [h, setH] = useState<History | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => {
    setH(null);
    api<History>(`/api/recommendations/history?species=${encodeURIComponent(species)}&weeks=${weeks}`).then(setH).catch((e: ApiError) => setErr(e.message));
  }, [species, weeks]);
  const go = (s: Species, w: number) => router.replace(`/record?species=${encodeURIComponent(s)}&weeks=${w}`, { scroll: false });
  const s = h?.summary;
  const shown = h ? (all ? h.days : h.days.slice(0, 14)) : [];

  return (
    <div className="mt-6 space-y-6">
      <div>
        <h1 className="text-[1.75rem] font-bold leading-tight tracking-tight sm:text-4xl">지나고 보니, 추천은 맞았나</h1>
        <p className="mt-1 max-w-3xl text-ink-2">위판 자료가 다 채워지는 7일 뒤에 결과를 확정하고 채점합니다. Top-3 가운데 실제로 평소의 1.5배 이상 팔린(좋은 날) 권역의 비율이 P@3 입니다.</p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="radiogroup" aria-label="품목" className="inline-flex rounded-lg border border-ink bg-white p-1">
          {SPECIES.map((x) => (
            <button key={x} role="radio" aria-checked={x === species} type="button" onClick={() => go(x, weeks)}
              className={`min-w-20 rounded-md px-4 py-2 font-semibold ${x === species ? "bg-ink text-paper" : "hover:bg-paper-2"}`}>{x}</button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-2">기간
          <select value={weeks} onChange={(e) => go(species, Number(e.target.value))} className="rounded border border-line bg-white px-2 py-1.5 text-ink">
            {WEEKS.map((w) => <option key={w} value={w}>최근 {w}주</option>)}
          </select>
        </label>
      </div>
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      {!h ? <p className="text-ink-2">채점 기록을 읽는 중…</p> : !s?.days ? <p className="rounded-lg border border-line bg-white p-4">이 기간에 결과가 확정된 날이 없습니다.</p> : (
        <>
          <section aria-label="요약" className="grid grid-cols-3 gap-2 sm:gap-3 lg:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.4fr)]">
            {[["보여 드린 추천", s.served, "text-buoy"], ["규칙(어제 좋았던 곳)", s.rule, "text-rule"], ["무작위로 골랐다면", s.random, "text-ink-2"]].map(([k, v, c]) => (
              <div key={k as string} className="rounded-lg border border-line bg-white p-3 sm:p-4">
                <p className="text-xs text-ink-2 sm:text-sm">{k as string}</p>
                <p className={`num text-2xl font-bold sm:text-4xl ${c}`}>{pct(v as number)}</p>
              </div>
            ))}
            <div className="col-span-3 flex flex-col justify-center rounded-lg border-2 border-ink bg-white p-4 lg:col-span-1">
              <p className="font-semibold">최근 {s.weeks}주 · 확정된 {s.days}일</p>
              <p className="text-ink-2">{verdict(Number(s.served), Number(s.rule))} 무작위보다는 {pct(Number(s.served) - Number(s.random))}p 높습니다.</p>
            </div>
          </section>
          <section className="rounded-lg border border-line bg-white p-4 sm:p-5">
            <h2 className="mb-3 font-bold">주별 적중률</h2>
            <WeeklyChart days={h.days} />
          </section>
          <section className="rounded-lg border border-line bg-white p-4 sm:p-5">
            <h2 className="mb-1 font-bold">날마다</h2>
            <p className="mb-3 text-sm text-ink-2"><span className="rounded bg-buoy px-1.5 text-white">채운 칸</span> = 실제로 좋은 날이었던 Top-3 권역 · 테두리 칸 = 아니었던 권역</p>
            <ol className="divide-y divide-line">
              {shown.map((d) => {
                const hits = d.top3.filter((a) => d.goodAreas.includes(a)).length;
                const missed = d.goodAreas.filter((a) => !d.top3.includes(a));
                return (
                  <li key={d.date} className="grid gap-2 py-3 sm:grid-cols-[8rem_minmax(0,1fr)_7.5rem] sm:items-center">
                    <span className="num font-semibold">{dayLabel(d.date)}</span>
                    <div>
                      <ul className="flex flex-wrap gap-1.5" aria-label="Top-3">
                        {d.top3.map((a, i) => {
                          const hit = d.goodAreas.includes(a);
                          return <li key={a} className={`rounded px-2 py-0.5 text-sm ${hit ? "bg-buoy font-semibold text-white" : "border border-line text-ink-2"}`}>
                            {i + 1}. {a}<span className="sr-only">{hit ? " — 좋은 날" : " — 아님"}</span></li>;
                        })}
                      </ul>
                      {missed.length > 0 && <p className="mt-1 text-xs text-ink-2">놓친 좋은 권역: {missed.join(" · ")}</p>}
                    </div>
                    <span className="num whitespace-nowrap sm:text-right"><b>{hits}/3</b> <span className="text-xs text-ink-2">규칙 {pct(d.ruleP)}</span></span>
                  </li>
                );
              })}
            </ol>
            {h.days.length > 14 && (
              <button type="button" onClick={() => setAll((v) => !v)} className="mt-2 text-sm font-semibold text-depth underline underline-offset-4">
                {all ? "최근 14일만" : `${h.days.length}일 모두 보기`}</button>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default function Page() {
  return <Suspense><Record /></Suspense>;
}
