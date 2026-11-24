"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { when } from "@/lib/admin";
import { AdminShell, Panel } from "@/components/admin/AdminShell";
import { llmLabel } from "@/components/rag/Answer";

interface RagStat { llm: string; mode: string; n: number; citeOkRate: number; numbersOkRate: number; unknownRate: number; helpfulYes: number | null; helpfulNo: number | null; avgSeconds: number }
interface RagRow { qaId: number; createdAt: string; mode: string; species: string | null; question: string; answer: string; citeOk: boolean; numbersOk: boolean | null; saidUnknown: boolean; madeUp: number; llm: string; seconds: number; helpful: boolean | null; who: string | null }
interface FbStat { modelVersion: string; species: string; n: number; helpfulYes: number; helpfulNo: number }
interface Comment { recDate: string; species: string; areaName: string; modelVersion: string; helpful: boolean; comment: string; createdAt: string; who: string | null }
interface Audit { auditId: number; action: string; target: string | null; detail: string | null; createdAt: string; who: string | null }
interface Usage { days: number; ragStats: RagStat[]; ragLog: RagRow[]; feedbackStats: FbStat[]; comments: Comment[]; audit: Audit[] }

const p = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(Number(v) * 100)}%`);
const ok = (v: boolean | null | undefined, yes: string, no: string) =>
  v == null ? <span className="text-ink-2">—</span> : v ? <span className="text-depth">✓ {yes}</span> : <span className="font-semibold text-buoy">✕ {no}</span>;

export default function UsagePage() {
  const [u, setU] = useState<Usage | null>(null);
  const [problems, setProblems] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<Usage>(`/api/admin/usage?days=30&problemsOnly=${problems}`).then(setU).catch((e: ApiError) => setErr(e.message)), [problems]);
  useEffect(() => { load(); }, [load]);
  return (
    <AdminShell title="이용 기록" lead="물어보기 · 근거 설명의 답이 근거를 지켰는지, 사람들이 추천을 어떻게 느꼈는지 봅니다. 숫자 검사에 걸린 답과 ‘아니에요’를 받은 답부터 살펴보세요.">
      {err && <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft p-3">{err}</p>}
      {u && (
        <div className="space-y-5">
          <Panel title={`답 품질 — 최근 ${u.days}일`}>
            <div className="overflow-x-auto">
              <table className="num w-full min-w-[40rem] text-sm">
                <thead className="text-left text-ink-2"><tr><th className="py-1">LLM</th><th>쓰임</th><th className="text-right">답</th><th className="text-right">인용 정상</th><th className="text-right">숫자 정상</th><th className="text-right">모른다고 답</th><th className="text-right">도움 됨 / 아님</th><th className="text-right">평균 시간</th></tr></thead>
                <tbody>
                  {u.ragStats.map((r) => (
                    <tr key={r.llm + r.mode} className="border-t border-line">
                      <td className="py-1.5">{llmLabel(r.llm)}</td><td>{r.mode === "ask" ? "물어보기" : "근거 설명"}</td><td className="text-right">{r.n}</td>
                      <td className="text-right">{p(r.citeOkRate)}</td>
                      <td className={`text-right ${r.numbersOkRate < 1 ? "font-semibold text-buoy" : ""}`}>{p(r.numbersOkRate)}</td>
                      <td className="text-right">{p(r.unknownRate)}</td><td className="text-right">{r.helpfulYes ?? 0} / {r.helpfulNo ?? 0}</td>
                      <td className="text-right">{Number(r.avgSeconds).toFixed(1)}초</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="질문과 답" note={<label className="flex items-center gap-2"><input type="checkbox" checked={problems} onChange={(e) => setProblems(e.target.checked)} />문제 있는 답만</label>}>
            {u.ragLog.length === 0 ? <p className="text-sm text-ink-2">해당하는 답이 없습니다.</p> : (
              <ol className="divide-y divide-line">
                {u.ragLog.map((r) => (
                  <li key={r.qaId} className="py-3">
                    <p className="text-xs text-ink-2"><span className="num">{when(r.createdAt)}</span> · {r.who ?? "—"} · {r.mode === "ask" ? "물어보기" : "근거 설명"} · {llmLabel(r.llm)} · {Number(r.seconds).toFixed(1)}초</p>
                    <p className="mt-0.5 font-semibold">{r.question}</p>
                    <p className="mt-0.5 line-clamp-2 text-sm text-ink-2">{r.answer}</p>
                    <p className="mt-1 flex flex-wrap gap-x-4 text-xs">
                      {ok(r.citeOk, "인용", r.saidUnknown ? "모른다고 답" : "인용 없음")}{ok(r.numbersOk, "숫자", "근거에 없는 숫자")}
                      {r.madeUp > 0 && <span className="font-semibold text-buoy">✕ 없는 근거 인용 {r.madeUp}개</span>}
                      {ok(r.helpful, "도움이 됐어요", "아니에요")}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="추천 피드백 — 서비스하던 모델별">
              {u.feedbackStats.length === 0 ? <p className="text-sm text-ink-2">아직 피드백이 없습니다.</p> : (
                <table className="num w-full text-sm">
                  <thead className="text-left text-ink-2"><tr><th className="py-1">모델</th><th>품목</th><th className="text-right">도움 됨</th><th className="text-right">아님</th></tr></thead>
                  <tbody>{u.feedbackStats.map((f) => (
                    <tr key={f.modelVersion + f.species} className="border-t border-line"><td className="py-1.5">{f.modelVersion}</td><td>{f.species}</td>
                      <td className="text-right">{f.helpfulYes}</td><td className="text-right">{f.helpfulNo}</td></tr>))}</tbody>
                </table>
              )}
              {u.comments.length > 0 && (
                <ul className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
                  {u.comments.map((c, i) => <li key={i}><span className="text-ink-2">{c.recDate} {c.species} {c.areaName} · {c.helpful ? "도움 됨" : "아님"} · {c.who}</span><br />“{c.comment}”</li>)}
                </ul>
              )}
            </Panel>
            <Panel title="관리자 행동 기록">
              <ul className="divide-y divide-line text-sm">
                {u.audit.map((a) => (
                  <li key={a.auditId} className="flex flex-wrap gap-x-3 py-1.5"><span className="num text-ink-2">{when(a.createdAt)}</span><b>{a.who}</b>
                    <span>{a.action}</span>{a.detail && <span className="text-ink-2">{a.detail}</span>}</li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}
    </AdminShell>
  );
}
