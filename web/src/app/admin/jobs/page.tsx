"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { JOB, when, type JobRun } from "@/lib/admin";
import { AdminShell, Chip, Panel } from "@/components/admin/AdminShell";

function secs(a: string, b: string | null) {
  if (!b) return "—";
  const s = (new Date(b).getTime() - new Date(a).getTime()) / 1000;
  return s < 60 ? `${s.toFixed(0)}초` : `${(s / 60).toFixed(1)}분`;
}

function Jobs() {
  const sp = useSearchParams();
  const router = useRouter();
  const [rows, setRows] = useState<JobRun[] | null>(null);
  const [detail, setDetail] = useState<JobRun | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = sp.get("run");
  useEffect(() => { api<JobRun[]>("/api/admin/jobs?limit=60").then(setRows).catch((e: ApiError) => setErr(e.message)); }, []);
  useEffect(() => {
    if (!run) { setDetail(null); return; }
    api<JobRun>(`/api/admin/jobs/${run}`).then(setDetail).catch((e: ApiError) => setErr(e.message));
  }, [run]);
  return (
    <AdminShell title="작업 기록" lead="정해진 시각 · 관리자 요청 · 명령줄 어디서 돌렸든 같은 표(job_run)에 남습니다. 실패도 남습니다.">
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="overflow-x-auto rounded-lg border border-line bg-white">
          <table className="num w-full min-w-[30rem] text-sm">
            <thead className="border-b border-line bg-paper text-left text-ink-2"><tr><th className="px-3 py-2">#</th><th className="px-2">시작</th><th className="px-2">작업</th><th className="px-3 text-right">결과</th></tr></thead>
            <tbody>
              {rows?.map((j) => (
                <tr key={j.runId} onClick={() => router.replace(`/admin/jobs?run=${j.runId}`, { scroll: false })}
                  className={`cursor-pointer border-t border-line align-top hover:bg-paper ${String(j.runId) === run ? "bg-buoy-soft/40" : ""}`}>
                  <td className="px-3 py-2.5 text-ink-2">{j.runId}</td><td className="whitespace-nowrap px-2 py-2.5">{when(j.startedAt)}</td>
                  <td className="px-2 py-2.5"><b>{JOB[j.job] ?? j.job}</b> <span className="text-xs text-ink-2">· {secs(j.startedAt, j.endedAt)} · {j.triggerBy}</span>
                    <div className="text-xs text-ink-2">{j.summary}</div></td>
                  <td className="px-3 py-2.5 text-right"><Chip k={j.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail ? (
          <Panel title={`#${detail.runId} ${JOB[detail.job] ?? detail.job}`} note={<Chip k={detail.status} />}>
            <p className="mb-3">{detail.summary}</p>
            <p className="mb-1 text-sm text-ink-2">자세한 기록 (job_run.detail)</p>
            <pre className="max-h-[36rem] overflow-auto rounded bg-ink p-3 text-xs leading-relaxed text-paper">{JSON.stringify(detail.detail, null, 2)}</pre>
          </Panel>
        ) : <p className="text-ink-2">왼쪽에서 작업을 고르면 자세한 기록이 보입니다.</p>}
      </div>
    </AdminShell>
  );
}

export default function Page() {
  return <Suspense><Jobs /></Suspense>;
}
