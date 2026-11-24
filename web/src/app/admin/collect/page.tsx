"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { SOURCE, when, type CollectLog, type CollectSource, type JobRun } from "@/lib/admin";
import { AdminShell, Chip, Panel } from "@/components/admin/AdminShell";
import { JobStatus, useJob } from "@/components/admin/JobRunner";
import { useAuth } from "@/lib/auth";

interface Data { sources: CollectSource[]; log: CollectLog[]; lastRun: JobRun | Record<string, never> }

export default function Collect() {
  const [d, setD] = useState<Data | null>(null);
  const [failOnly, setFailOnly] = useState(false);
  const [fail, setFail] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const { ready } = useAuth();
  const load = useCallback(() => api<Data>(`/api/admin/collect?limit=120&failOnly=${failOnly}`).then(setD).catch((e: ApiError) => setErr(e.message)), [failOnly]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (ready) api<{ demo: boolean }>("/api/meta").then((m) => setDemo(m.demo)).catch(() => undefined); }, [ready]);
  const { q, err: jerr, busy, start } = useJob(load);
  return (
    <AdminShell title="수집" lead="출처마다 매일 받아 DB 에 넣습니다. 한 번의 시도가 한 줄 — 실패도 지우지 않고 남겨, 교체 조건 1(데이터 상태)의 근거가 됩니다.">
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      {d && (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {d.sources.map((s) => {
              const rate = s.n7d ? s.ok7d / s.n7d : null;
              const bad = rate != null && rate < 0.95;
              return (
                <section key={s.source} className={`rounded-lg border bg-white p-4 ${bad ? "border-buoy" : "border-line"}`}>
                  <h2 className="font-bold">{SOURCE[s.source] ?? s.source}</h2>
                  <p className={`num mt-1 text-3xl font-bold ${bad ? "text-buoy" : ""}`}>{rate == null ? "—" : `${Math.round(rate * 100)}%`}</p>
                  <p className="num text-sm text-ink-2">최근 7일 {s.ok7d}/{s.n7d} · 24시간 {s.rows24h.toLocaleString()}행</p>
                  <p className="mt-2 text-sm">마지막 성공 <span className="num">{when(s.lastOk)}</span></p>
                  {s.lastFail && <p className="mt-1 text-sm text-buoy">마지막 실패 {when(s.lastFail)}<br /><span className="text-ink-2">{s.lastFailNote}</span></p>}
                </section>
              );
            })}
          </div>
          <Panel title="지금 수집" note={"lastRun" in d && d.lastRun && "summary" in d.lastRun ? <>최근: {when(d.lastRun.startedAt)} {d.lastRun.summary}</> : null}>
            <div className="flex flex-wrap items-end gap-3">
              <button type="button" disabled={busy} onClick={() => start("/api/admin/jobs/collect_daily", fail ? { simulate_fail: fail } : {})}
                className="rounded-md bg-ink px-4 py-2 font-semibold text-paper disabled:opacity-50">수집 실행</button>
              {demo && (
                <label className="flex items-center gap-2 rounded-md border border-dashed border-gale bg-gale-soft/40 px-3 py-1.5 text-sm">
                  시연: 관측 실패 흉내
                  <select value={fail} onChange={(e) => setFail(Number(e.target.value))} className="rounded border border-line bg-white px-2 py-1">
                    <option value={0}>없음</option><option value={10}>10%</option><option value={30}>30%</option>
                  </select>
                </label>
              )}
            </div>
            <div className="mt-3"><JobStatus q={q} err={jerr} /></div>
            {demo && <p className="mt-2 text-xs text-ink-2">시연 모드에서는 OpenAPI 를 부르지 않고 받아 둔 원본을 다시 적재하며 기록을 ‘재생’으로 남깁니다. 실제 운영은 .env 에 키를 넣고 DEMO_TODAY 를 비우면 됩니다.</p>}
          </Panel>
          <Panel title="수집 기록" note={
            <label className="flex items-center gap-2"><input type="checkbox" checked={failOnly} onChange={(e) => setFailOnly(e.target.checked)} />실패만</label>}>
            <div className="max-h-[32rem] overflow-auto">
              <table className="num w-full min-w-[36rem] text-sm">
                <thead className="sticky top-0 bg-white text-left text-ink-2"><tr><th className="py-1">시각</th><th>출처</th><th>대상</th><th>결과</th><th className="text-right">행</th><th className="pl-4">메모</th></tr></thead>
                <tbody>
                  {d.log.map((l) => (
                    <tr key={l.logId} className="border-t border-line align-top">
                      <td className="py-1.5 whitespace-nowrap text-ink-2">{when(l.logged)}</td><td>{SOURCE[l.source] ?? l.source}</td>
                      <td className="whitespace-nowrap">{l.target}</td><td><Chip k={l.status} /></td>
                      <td className="text-right">{l.nRows.toLocaleString()}</td><td className="pl-4 text-ink-2">{l.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </AdminShell>
  );
}
