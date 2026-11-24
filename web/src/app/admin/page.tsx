"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ACTION, JOB, KIND, SOURCE, n3, when, type Overview } from "@/lib/admin";
import { AdminShell, Chip, Panel } from "@/components/admin/AdminShell";
import { JobButtons } from "@/components/admin/JobRunner";

function Champion({ o }: { o: Overview }) {
  const c = o.champion;
  if (!c) return <Panel title="지금 서비스 중인 모델"><p>챔피언이 없습니다 — 시연 초기화(bootstrap_demo)를 먼저 돌리세요.</p></Panel>;
  return (
    <Panel title="지금 서비스 중인 모델" note={<Link href={`/admin/models?v=${c.version}`} className="text-depth underline underline-offset-4">자세히</Link>}>
      <p className="text-2xl font-bold tracking-tight">{c.version}</p>
      <p className="text-ink-2">{KIND[c.kind] ?? c.kind} · {when(c.promotedAt)} 부터 챔피언</p>
      <dl className="num mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded bg-paper p-2"><dt className="text-xs text-ink-2">평가 P@3</dt><dd className="text-xl font-bold">{n3(c.pAt3)}</dd></div>
        <div className="rounded bg-paper p-2"><dt className="text-xs text-ink-2">같은 창 규칙</dt><dd className="text-xl">{n3(c.rulePAt3 ?? c.champPAt3)}</dd></div>
        <div className="rounded bg-paper p-2"><dt className="text-xs text-ink-2">평가 창</dt><dd className="text-sm leading-7">{c.evalFrom?.slice(5) ?? "—"} ~ {c.evalUntil?.slice(5) ?? "—"}</dd></div>
      </dl>
      {c.decision && <p className="mt-3 text-sm text-ink-2">{c.decision}</p>}
      {o.lastRetrain && (
        <p className="mt-3 border-t border-line pt-3 text-sm">
          <span className="font-semibold">최근 재학습</span> {when(o.lastRetrain.startedAt)} — {o.lastRetrain.summary}
        </p>
      )}
    </Panel>
  );
}

function CollectMini({ o }: { o: Overview }) {
  return (
    <Panel title="수집 — 최근 7일" note={<Link href="/admin/collect" className="text-depth underline underline-offset-4">기록 보기</Link>}>
      {o.collect.length === 0 ? <p className="text-sm text-ink-2">수집 기록이 없습니다. 수집을 한 번 실행해 보세요.</p> : (
        <ul className="space-y-2.5">
          {o.collect.map((s) => {
            const rate = s.n7d ? s.ok7d / s.n7d : null;
            return (
              <li key={s.source}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-semibold">{SOURCE[s.source] ?? s.source}</span>
                  <span className={`num ${rate != null && rate < 0.95 ? "font-semibold text-buoy" : "text-ink-2"}`}>
                    {rate == null ? "—" : `${Math.round(rate * 100)}%`} <span className="text-ink-2">({s.ok7d}/{s.n7d})</span>
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded bg-paper-2" aria-hidden>
                  <div className={`h-full rounded ${rate != null && rate < 0.95 ? "bg-buoy" : "bg-depth"}`} style={{ width: `${(rate ?? 0) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-3 text-xs text-ink-2">교체 조건 1: 전체 성공률이 95% 아래면 재학습 결과가 좋아도 교체하지 않습니다.</p>
    </Panel>
  );
}

export default function AdminHome() {
  const [o, setO] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<Overview>("/api/admin/overview").then(setO).catch((e: ApiError) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  return (
    <AdminShell title="관리자" lead="수집 · 추천 계산 · 채점 · 재학습은 정해진 시각에 저절로 돌고, 여기서 같은 작업을 손으로 돌릴 수도 있습니다. 실행은 요청만 남기고 작업 프로세스가 가져가 처리합니다.">
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      {!o ? <p className="text-ink-2">불러오는 중…</p> : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <div className="space-y-5">
            <Champion o={o} />
            <Panel title="작업 실행" note={o.demo ? "시연 모드 — 수집은 받아 둔 원본을 다시 적재" : undefined}>
              <JobButtons runnable={o.runnable} onDone={load} />
            </Panel>
            <Panel title="최근 작업" note={<Link href="/admin/jobs" className="text-depth underline underline-offset-4">전체</Link>}>
              <ul className="divide-y divide-line text-sm">
                {o.jobs.map((j) => (
                  <li key={j.runId} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2">
                    <span className="num w-24 shrink-0 text-ink-2">{when(j.startedAt)}</span>
                    <Chip k={j.status} />
                    <Link href={`/admin/jobs?run=${j.runId}`} className="font-semibold hover:underline">{JOB[j.job] ?? j.job}</Link>
                    <span className="min-w-0 basis-full text-ink-2 sm:basis-auto sm:flex-1">{j.summary}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
          <div className="space-y-5">
            <CollectMini o={o} />
            <Panel title="교체 기록" note={<Link href="/admin/models" className="text-depth underline underline-offset-4">모델 목록</Link>}>
              <ol className="space-y-2.5 text-sm">
                {o.promotions.map((p) => (
                  <li key={p.logId}>
                    <div className="flex items-baseline gap-2"><Chip k={p.action}>{ACTION[p.action] ?? p.action}</Chip>
                      <span className="num text-ink-2">{when(p.at)}</span><span className="text-ink-2">{p.actor}</span></div>
                    <p className="mt-0.5"><span className="text-ink-2">{p.fromVersion ?? "—"}</span> → <b>{p.toVersion}</b></p>
                    {p.reason && <p className="text-ink-2">{p.reason}</p>}
                  </li>
                ))}
              </ol>
            </Panel>
            <Panel title="정해진 시각">
              <ul className="space-y-1 text-sm">
                {o.schedule.map((s) => <li key={s.job} className="flex justify-between gap-2"><span className="num text-ink-2">{s.time}</span><span>{JOB[s.job]}</span></li>)}
              </ul>
              {o.demo && <p className="mt-2 text-xs text-ink-2">시연 모드에서는 정해진 시각에 돌지 않습니다 (날짜가 고정이라). 손으로 실행한 요청만 처리합니다.</p>}
            </Panel>
          </div>
        </div>
      )}
    </AdminShell>
  );
}
