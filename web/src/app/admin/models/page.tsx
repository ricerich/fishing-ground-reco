"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { KIND, STATUS, n3, signed, when, type ModelRow } from "@/lib/admin";
import { AdminShell, Chip, Panel } from "@/components/admin/AdminShell";
import { Gates } from "@/components/admin/Gates";
import { JobStatus, useJob } from "@/components/admin/JobRunner";

const SP = ["고등어", "방어", "삼치"];

function Detail({ m, onChanged }: { m: ModelRow; onChanged: () => void }) {
  const { q, err, busy, start } = useJob(onChanged);
  const canRollback = m.status === "retired" || (m.kind === "rule" && m.status !== "champion");
  return (
    <Panel title={m.version} note={<span className="flex items-center gap-2"><Chip k={m.status}>{STATUS[m.status]}</Chip>{KIND[m.kind]}</span>}>
      <div className="space-y-5">
        {m.decision && <p className="rounded-md bg-paper px-3 py-2">{m.decision}</p>}
        <dl className="num grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          <dt className="text-ink-2">학습</dt><dd>{m.fitFrom ?? "—"} ~ {m.fitUntil ?? "—"}</dd>
          <dt className="text-ink-2">평가 창</dt><dd>{m.evalFrom ?? "—"} ~ {m.evalUntil ?? "—"}</dd>
          <dt className="text-ink-2">학습 행</dt><dd>{m.nTrain?.toLocaleString() ?? "—"}</dd>
          <dt className="text-ink-2">평가 묶음</dt><dd>{m.nGroups ?? "—"}개 (품목 × 날짜)</dd>
          <dt className="text-ink-2">P@3</dt><dd className="font-semibold">{n3(m.pAt3)}</dd>
          <dt className="text-ink-2">비교한 챔피언</dt><dd>{m.champVersion ? `${m.champVersion} ${n3(m.champPAt3)}` : "—"}</dd>
          <dt className="text-ink-2">규칙(같은 창)</dt><dd>{n3(m.rulePAt3)}</dd>
          <dt className="text-ink-2">요일 · 평년 기준</dt><dd>{m.statsUntil ?? "—"} 까지</dd>
        </dl>
        <div>
          <h3 className="mb-2 font-semibold">교체 조건 5개</h3>
          <Gates m={m} />
        </div>
        {m.perSpecies && (
          <div>
            <h3 className="mb-2 font-semibold">품목별 P@3</h3>
            <table className="num w-full text-sm">
              <thead className="text-left text-ink-2"><tr><th className="py-1">품목</th><th>이 모델</th><th>챔피언</th><th>규칙</th><th className="text-right">평가일</th></tr></thead>
              <tbody>
                {SP.map((s) => { const v = m.perSpecies?.[s]; return v && (
                  <tr key={s} className="border-t border-line">
                    <td className="py-1.5">{s}</td><td className="font-semibold">{n3(v.p)}</td><td>{n3(v.champ)}</td><td>{n3(v.rule)}</td>
                    <td className="text-right">{v.days}</td>
                  </tr>); })}
              </tbody>
            </table>
          </div>
        )}
        {canRollback && (
          <div className="space-y-2 border-t border-line pt-4">
            <p className="text-sm text-ink-2">되돌리기는 교체 조건을 거치지 않고 바로 챔피언을 바꿉니다. 이 모델 파일로 오늘 추천을 다시 계산하고, 기록에는 ‘되돌리기’로 남습니다.</p>
            <button type="button" disabled={busy} onClick={() => start(`/api/admin/models/${m.version}/rollback`)}
              className="rounded-md bg-ink px-4 py-2 font-semibold text-paper disabled:opacity-50">{m.version} 로 되돌리기</button>
          </div>
        )}
        <JobStatus q={q} err={err} />
      </div>
    </Panel>
  );
}

function Models() {
  const sp = useSearchParams();
  const router = useRouter();
  const [rows, setRows] = useState<ModelRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<ModelRow[]>("/api/admin/models").then(setRows).catch((e: ApiError) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const v = sp.get("v") ?? rows?.find((r) => r.gates)?.version ?? rows?.[0]?.version;
  const sel = rows?.find((r) => r.version === v);
  return (
    <AdminShell title="모델 · 교체" lead="재학습 때마다 후보가 생기고, 같은 평가 창에서 챔피언 · 규칙과 비교해 조건 5개를 모두 통과해야 챔피언이 바뀝니다. 통과하지 못한 후보도 이유와 함께 남깁니다.">
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      {!rows ? <p className="text-ink-2">불러오는 중…</p> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
          <div className="overflow-x-auto rounded-lg border border-line bg-white">
            <table className="num w-full min-w-[28rem] text-sm">
              <thead className="border-b border-line bg-paper text-left text-ink-2">
                <tr><th className="px-3 py-2">버전</th><th className="px-2">상태</th><th className="px-2 text-right">P@3</th><th className="px-3 text-right">챔피언 대비 · 95% 구간</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.version} onClick={() => router.replace(`/admin/models?v=${r.version}`, { scroll: false })}
                    className={`cursor-pointer border-t border-line hover:bg-paper ${r.version === v ? "bg-buoy-soft/40 outline outline-2 -outline-offset-2 outline-buoy" : ""}`}>
                    <td className="px-3 py-2"><button type="button" className="text-left font-semibold">{r.version}</button><div className="text-xs text-ink-2">{KIND[r.kind]} · {when(r.createdAt)}</div></td>
                    <td className="px-2"><Chip k={r.status}>{STATUS[r.status]}</Chip></td>
                    <td className="px-2 text-right font-semibold">{n3(r.pAt3)}</td>
                    <td className="px-3 text-right">
                      <span className={r.diff != null && r.diff >= 0.01 ? "font-semibold text-buoy" : ""}>{r.champVersion ? signed(r.diff) : "—"}</span>
                      {r.ciLow != null && <div className="text-xs text-ink-2">[{signed(r.ciLow)}, {signed(r.ciHigh)}]</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sel && <Detail key={sel.version} m={sel} onChanged={load} />}
        </div>
      )}
    </AdminShell>
  );
}

export default function Page() {
  return <Suspense><Models /></Suspense>;
}
