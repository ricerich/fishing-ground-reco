"use client";
// RAG 답 한 덩어리 — 글(인용은 작은 번호표) · 근거 목록 · 검사 결과 · 도움 여부
import { useState } from "react";
import { sendFeedback, splitCites, type Check, type Source } from "@/lib/rag";

export interface AnswerState {
  text: string; llm?: string; notice?: string; sources: Source[]; facts?: string | null;
  check?: Check; seconds?: number; qaId?: number; done: boolean; error?: string;
}

export const emptyAnswer = (): AnswerState => ({ text: "", sources: [], done: false });

export function llmLabel(llm?: string) {
  if (!llm) return "";
  return llm === "mock" ? "LLM 없이 근거 문장 모음" : llm.replace(/^ollama:/, "Ollama · ").replace(/^openai:/, "OpenAI · ").replace(/^claude:/, "Claude · ");
}

function CiteTag({ id, sources }: { id: string; sources: Source[] }) {
  if (id === "추천") return <span className="mx-0.5 rounded bg-buoy-soft px-1 align-[0.15em] text-[0.7rem] font-semibold text-buoy" title="추천 표의 숫자">추천</span>;
  const n = sources.findIndex((s) => s.id === id);
  return (
    <a href={`#src-${id}`} className={`mx-0.5 rounded px-1 align-[0.15em] text-[0.7rem] font-semibold ${n >= 0 ? "bg-depth-soft text-depth" : "bg-buoy text-white"}`}
      title={n >= 0 ? sources[n].title : "근거 목록에 없는 번호"}>{n >= 0 ? n + 1 : "?"}</a>
  );
}

export function AnswerView({ a, showFacts = true }: { a: AnswerState; showFacts?: boolean }) {
  const [fb, setFb] = useState<boolean | null>(null);
  const c = a.check;
  return (
    <div className="space-y-3">
      {a.notice && <p role="status" className="rounded border-l-4 border-gale bg-gale-soft px-3 py-2 text-sm">{a.notice}</p>}
      {a.error ? <p role="alert" className="rounded border-l-4 border-buoy bg-buoy-soft px-3 py-2">{a.error}</p> : (
        <p className="whitespace-pre-wrap text-[1.05rem] leading-8" aria-live="polite" aria-busy={!a.done}>
          {splitCites(a.text).map((p, i) => p.t === "text" ? <span key={i}>{p.v}</span> : <CiteTag key={i} id={p.v} sources={a.sources} />)}
          {!a.done && <span className="ml-0.5 inline-block h-5 w-2 animate-pulse bg-ink align-middle" aria-hidden />}
        </p>
      )}
      {a.done && c && (
        <ul className="flex flex-wrap gap-2 text-xs" aria-label="답 검사">
          <li className={`rounded px-2 py-1 ${c.cite_ok ? "bg-depth-soft" : "bg-paper-2"}`}>{c.cite_ok ? "✓ 인용이 모두 실제 근거" : c.said_unknown ? "자료에 없다고 답함" : "인용 없음"}</li>
          {c.made_up.length > 0 && <li className="rounded bg-buoy px-2 py-1 text-white">✕ 없는 근거 인용 {c.made_up.length}개</li>}
          <li className={`rounded px-2 py-1 ${c.numbers_ok ? "bg-depth-soft" : "bg-buoy text-white"}`}>
            {c.numbers_ok ? "✓ 숫자가 모두 근거에 있음" : `✕ 근거에 없는 숫자: ${c.unknown_numbers.join(", ")}`}
          </li>
          <li className="rounded bg-paper-2 px-2 py-1 text-ink-2">{llmLabel(a.llm)} · {a.seconds?.toFixed(1)}초</li>
        </ul>
      )}
      {showFacts && a.facts && (
        <details className="rounded-md border border-line bg-paper/60 px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold">이 설명에 쓴 숫자 (추천 표)</summary>
          <pre className="mt-2 whitespace-pre-wrap font-sans text-ink-2">{a.facts.replace(/<\/?추천>\n?/g, "")}</pre>
        </details>
      )}
      {a.sources.length > 0 && (
        <details className="rounded-md border border-line px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold">근거 문서 {a.sources.length}개</summary>
          <ol className="mt-2 space-y-2">
            {a.sources.map((s, i) => (
              <li key={s.id} id={`src-${s.id}`} className="scroll-mt-24">
                <p><b className="text-depth">{i + 1}</b> {s.title} · {s.section}
                  {s.sample && <span className="ml-1 rounded bg-gale-soft px-1 text-xs">수업용 예시</span>}</p>
                <p className="mt-0.5 line-clamp-3 text-ink-2">{s.text}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
      {a.done && a.qaId && (
        <div className="flex items-center gap-2 text-sm">
          {fb === null ? (
            <>
              <span className="text-ink-2">도움이 됐나요?</span>
              {[true, false].map((v) => (
                <button key={String(v)} type="button" onClick={() => sendFeedback(a.qaId!, v).then(() => setFb(v)).catch(() => undefined)}
                  className="rounded border border-line px-2.5 py-1 hover:border-ink">{v ? "도움이 됐어요" : "아니에요"}</button>
              ))}
            </>
          ) : <span role="status" className="text-depth">의견을 남겼습니다. 답 품질 점검에 씁니다.</span>}
        </div>
      )}
    </div>
  );
}

/** 이벤트를 상태에 쌓는 리듀서 — 설명 패널 · 문답 화면이 함께 쓴다 */
export function reduceAnswer(a: AnswerState, e: import("@/lib/rag").RagEvent): AnswerState {
  switch (e.type) {
    case "meta": return { ...a, llm: e.llm, sources: e.sources, facts: e.facts };
    case "notice": return { ...a, notice: e.text };
    case "delta": return { ...a, text: a.text + e.text };
    case "done": return { ...a, text: e.answer || a.text, check: e.check, llm: e.llm, seconds: e.seconds, done: true };
    case "logged": return { ...a, qaId: e.qaId };
  }
}
