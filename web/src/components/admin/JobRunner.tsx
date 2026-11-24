"use client";
// 작업 실행 — 요청(202) → 요청 번호로 1.5초마다 상태 확인 → 끝나면 한 줄 요약
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { JOB, type QueueItem } from "@/lib/admin";
import { Chip } from "./AdminShell";

export function useJob(onDone?: (q: QueueItem) => void) {
  const [q, setQ] = useState<QueueItem | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const poll = (id: number) => {
    api<QueueItem>(`/api/admin/queue/${id}`).then((x) => {
      setQ(x);
      if (x.done) done.current?.(x);
      else timer.current = setTimeout(() => poll(id), 1500);
    }).catch((e: ApiError) => setErr(e.message));
  };
  const start = async (path: string, body?: unknown) => {
    setErr(null);
    try {
      const r = await api<{ queue_id: number; job: string; status: string }>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
      setQ({ queueId: r.queue_id, job: r.job, status: r.status, params: {}, requestedBy: "", requestedAt: "", runId: null });
      timer.current = setTimeout(() => poll(r.queue_id), 800);
    } catch (e) {
      setErr((e as ApiError).message);
    }
  };
  const busy = !!q && !q.done && !err;
  return { q, err, busy, start };
}

export function JobStatus({ q, err }: { q: QueueItem | null; err: string | null }) {
  if (err) return <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft px-3 py-2 text-sm">{err}</p>;
  if (!q) return null;
  const running = !q.done;
  return (
    <div role="status" aria-live="polite" className={`rounded-md border px-3 py-2.5 text-sm ${running ? "border-gale bg-gale-soft/60" : q.runStatus === "fail" ? "border-buoy bg-buoy-soft" : "border-depth bg-depth-soft/60"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">요청 #{q.queueId} {JOB[q.job] ?? q.job}</span>
        <Chip k={running ? q.status : (q.runStatus ?? q.status)}>{running ? (q.status === "queued" ? "대기 — 작업 프로세스가 곧 가져감" : "실행 중…") : q.runStatus === "fail" ? "실패" : "끝남"}</Chip>
        {q.runId && <Link href={`/admin/jobs?run=${q.runId}`} className="ml-auto text-depth underline underline-offset-4">작업 기록 #{q.runId}</Link>}
      </div>
      {q.summary && <p className="mt-1.5 text-ink">{q.summary}</p>}
    </div>
  );
}

/** 버튼 줄 + 상태 한 칸. demo 시나리오 버튼은 점선으로 구분 */
export function JobButtons({ runnable, onDone }: { runnable: Record<string, string>; onDone?: () => void }) {
  const { q, err, busy, start } = useJob(() => onDone?.());
  return (
    <div className="space-y-3">
      <ul className="grid gap-2 sm:grid-cols-2">
        {Object.entries(runnable).map(([k, desc]) => {
          const demo = k.startsWith("demo_");
          return (
            <li key={k}>
              <button type="button" disabled={busy} onClick={() => start(`/api/admin/jobs/${k}`)}
                className={`flex h-full w-full flex-col items-start rounded-md border px-3 py-2 text-left hover:border-ink disabled:opacity-50 ${demo ? "border-dashed border-gale bg-gale-soft/40" : "border-line bg-paper/40"}`}>
                <span className="font-semibold">{JOB[k] ?? k} 실행</span>
                <span className="text-xs text-ink-2">{desc}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <JobStatus q={q} err={err} />
    </div>
  );
}
