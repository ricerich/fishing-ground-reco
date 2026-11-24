"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api, ApiError } from "@/lib/api";
import type { Area, Item, Meta, Recommendation, Species } from "@/lib/types";
import { addDays, dayLabel, fillNote, modelName, pct, weight } from "@/lib/format";
import { CoastChart } from "@/components/CoastChart";
import { RankList } from "@/components/RankList";
import { useAuth } from "@/lib/auth";
import { ExplainPanel } from "@/components/rag/ExplainPanel";
import { FeedbackButtons, type FeedbackMap } from "@/components/FeedbackButtons";

const SPECIES: Species[] = ["고등어", "방어", "삼치"];

function Controls({ meta, species, date, onChange }: {
  meta: Meta; species: Species; date: string; onChange: (s: Species, d: string) => void;
}) {
  const tomorrow = addDays(meta.today, 1);
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div role="radiogroup" aria-label="품목" className="inline-flex rounded-lg border border-ink bg-white p-1">
        {SPECIES.map((s) => (
          <button key={s} role="radio" aria-checked={s === species} type="button" onClick={() => onChange(s, date)}
            className={`min-w-20 rounded-md px-4 py-2 text-base font-semibold ${s === species ? "bg-ink text-paper" : "text-ink hover:bg-paper-2"}`}>
            {s}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button type="button" onClick={() => onChange(species, meta.today)}
          className={`rounded border px-3 py-1.5 ${date === meta.today ? "border-ink bg-ink text-paper" : "border-line bg-white"}`}>
          오늘 {dayLabel(meta.today)}
        </button>
        <button type="button" onClick={() => onChange(species, tomorrow)}
          className={`rounded border px-3 py-1.5 ${date === tomorrow ? "border-ink bg-ink text-paper" : "border-line bg-white"}`}>
          내일
        </button>
        <label className="flex items-center gap-2 text-ink-2">
          지난 날
          <input type="date" value={date} min={meta.firstDate ?? undefined} max={meta.today}
            onChange={(e) => e.target.value && onChange(species, e.target.value)}
            className="rounded border border-line bg-white px-2 py-1 text-ink" />
        </label>
      </div>
    </div>
  );
}

function ModelNote({ rec }: { rec: Recommendation }) {
  if (!rec.run) return null;
  const r = rec.recent;
  const fill = fillNote(rec.run.yesterdayFill);
  return (
    <section aria-label="이 추천을 만든 방법" className="space-y-2 rounded-lg border border-line bg-white p-4 text-sm">
      <p>
        <span className="font-semibold">{modelName(rec.run.servedKind, rec.run.servedVersion)}</span>
        {" "}가 {rec.run.dataLastDay} 위판까지 보고 계산했습니다. 후보 {rec.run.candidates}곳.
      </p>
      {r && r.days ? (
        <p className="text-ink-2">
          최근 {r.weeks}주 중 결과가 확정된 {r.days}일, Top-3 가운데 실제로 평소보다 잘 잡힌 권역의 비율은
          <span className="num font-semibold text-ink"> 그동안 보여 드린 추천 {pct(r.served)}</span>,
          <span className="num"> 규칙(어제 좋았던 곳) {pct(r.rule)}</span>,
          <span className="num"> 무작위로 골랐다면 {pct(r.random)}</span>였습니다.
        </p>
      ) : null}
      <p className={fill.low ? "rounded bg-gale-soft px-2 py-1" : "text-ink-2"}>{fill.text}</p>
    </section>
  );
}

function Home() {
  const router = useRouter();
  const sp = useSearchParams();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [explain, setExplain] = useState<Item | null>(null);
  const [fb, setFb] = useState<FeedbackMap>({});
  const { me } = useAuth();
  const fav = me?.favoriteSpecies.find((s) => SPECIES.includes(s as Species)) as Species | undefined;
  const species = (SPECIES.includes(sp.get("species") as Species) ? sp.get("species") : fav ?? "방어") as Species;
  const date = sp.get("date") ?? meta?.today ?? "";

  useEffect(() => {
    Promise.all([api<Meta>("/api/meta"), api<Area[]>("/api/areas")])
      .then(([m, a]) => { setMeta(m); setAreas(a); })
      .catch((e: ApiError) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!date) return;
    setRec(null);
    setExplain(null);
    api<Recommendation>(`/api/recommendations?species=${encodeURIComponent(species)}&date=${date}`)
      .then(setRec).catch((e: ApiError) => setErr(e.message));
  }, [species, date]);

  useEffect(() => {
    if (!me || !date) { setFb({}); return; }
    api<{ area: string; helpful: boolean }[]>(`/api/feedback?date=${date}&species=${encodeURIComponent(species)}`)
      .then((rows) => setFb(Object.fromEntries(rows.map((r) => [r.area, r.helpful])))).catch(() => setFb({}));
  }, [me, species, date]);

  const change = useCallback((s: Species, d: string) => {
    router.replace(`/?species=${encodeURIComponent(s)}&date=${d}`, { scroll: false });
  }, [router]);

  if (err) return <p className="mt-8 rounded border-l-4 border-buoy bg-white p-4">불러오지 못했습니다: {err}</p>;
  if (!meta) return <p className="mt-8 text-ink-2">불러오는 중…</p>;

  const all: Item[] = rec ? [...rec.items, ...rec.others] : [];
  return (
    <div className="mt-6 space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-bold leading-tight tracking-tight sm:text-4xl">
          {dayLabel(date)} {species}, 평소보다 잘 잡힐 권역
        </h1>
        <p className="mt-1 text-ink-2">최근 위판 흐름으로 권역 14곳의 순서를 매겼습니다. 바다 상황은 경고로 따로 알립니다.</p>
      </div>
      <Controls meta={meta} species={species} date={date} onChange={change} />

      {!rec ? <p className="text-ink-2">계산된 추천을 읽는 중…</p> : !rec.available ? (
        <p className="rounded-lg border border-line bg-white p-4">{rec.message}</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <div className="space-y-4">
            <CoastChart areas={areas} items={all} excluded={rec.excluded.map((e) => e.area)} picked={picked} onPick={setPicked} />
          </div>
          <div className="space-y-5">
            <RankList items={rec.items} picked={picked} onPick={setPicked} favorites={me?.favoriteAreas}
              onExplain={(it) => { setExplain(it); setPicked(it.area); }}
              actions={me ? (it) => <FeedbackButtons date={date} species={species} area={it.area} value={fb[it.area]}
                onChange={(a, v) => setFb((m) => ({ ...m, [a]: v }))} /> : undefined} />
            {explain && <ExplainPanel species={species} date={date} area={explain.area} rank={explain.rank} onClose={() => setExplain(null)} />}
            <ModelNote rec={rec} />
            {rec.others.length > 0 && (
              <details className="rounded-lg border border-line bg-white p-4">
                <summary className="cursor-pointer font-semibold">나머지 후보 {rec.others.length}곳</summary>
                <table className="num mt-3 w-full text-sm">
                  <thead className="text-left text-ink-2"><tr><th className="py-1">순위</th><th>권역</th><th>평소</th><th className="text-right">점수</th></tr></thead>
                  <tbody>
                    {rec.others.map((o) => (
                      <tr key={o.area} className="border-t border-line">
                        <td className="py-1.5">{o.rank}</td><td>{o.area}</td><td>{weight(o.usualKg)}</td>
                        <td className="text-right">{o.score.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
            {rec.excluded.length > 0 && (
              <details className="rounded-lg border border-line bg-white p-4">
                <summary className="cursor-pointer font-semibold">순위에서 뺀 권역 {rec.excluded.length}곳</summary>
                <ul className="mt-2 space-y-1 text-sm">
                  {rec.excluded.map((e) => <li key={e.area}><span className="font-semibold">{e.area}</span> — {e.reason}</li>)}
                </ul>
              </details>
            )}
            <ul className="space-y-1 text-sm text-ink-2">
              {rec.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="mt-8 text-ink-2">불러오는 중…</p>}>
      <Home />
    </Suspense>
  );
}
