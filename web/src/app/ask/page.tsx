"use client";
// 규정 · 용어 · 서비스 문답 — 근거 문서에서 찾아 답하고, 근거가 없으면 없다고 말한다
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { streamRag } from "@/lib/rag";
import { AnswerView, emptyAnswer, reduceAnswer, type AnswerState } from "@/components/rag/Answer";

const EXAMPLES = ["점수가 0.5면 잡힐 확률이 50%인가요?", "평소보다 잘 잡힌 날은 어떻게 정하나요?", "모델은 언제 바뀌나요?",
  "어제 위판이 적게 보이는 이유는?", "적조주의보 기준이 뭐예요?", "고등어 금어기는 언제예요?"];

interface Turn { q: string; a: AnswerState }

export default function Ask() {
  const { me, ready } = useAuth();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const busy = turns.length > 0 && !turns[turns.length - 1].a.done;
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [turns.length]);

  const send = async (question: string) => {
    const text = question.trim();
    if (text.length < 2 || busy) return;
    setQ("");
    const history = turns.slice(-2).flatMap((t) => [{ role: "user", content: t.q }, { role: "assistant", content: t.a.text }]);
    const idx = turns.length;
    setTurns((ts) => [...ts, { q: text, a: emptyAnswer() }]);
    const upd = (f: (a: AnswerState) => AnswerState) => setTurns((ts) => ts.map((t, i) => (i === idx ? { ...t, a: f(t.a) } : t)));
    try {
      await streamRag("/api/rag/ask", { question: text, history }, (e) => upd((a) => reduceAnswer(a, e)));
    } catch (e) {
      upd((a) => ({ ...a, done: true, error: (e as ApiError).message }));
    }
  };

  return (
    <div className="mx-auto mt-8 max-w-3xl space-y-6">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-4xl">물어보기</h1>
        <p className="mt-1 text-ink-2">추천이 어떻게 만들어지는지, 바다 용어와 특보, 어촌 수칙을 근거 문서에서 찾아 답합니다. 문서에 없으면 없다고 답합니다.
          수칙 · 특보 문서는 <b className="text-ink">수업용 예시</b>라 실제 법령이 아닙니다.</p>
      </div>
      {!ready ? null : !me ? (
        <p className="rounded-lg border border-line bg-white p-4">회원만 물어볼 수 있습니다. <Link href="/login?next=/ask" className="font-semibold text-depth underline underline-offset-4">로그인</Link></p>
      ) : (
        <>
          {turns.length === 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="예시 질문">
              {EXAMPLES.map((e) => (
                <li key={e}><button type="button" onClick={() => send(e)} className="rounded-full border border-line bg-white px-3 py-1.5 text-sm hover:border-ink">{e}</button></li>
              ))}
            </ul>
          )}
          <ol className="space-y-6" aria-label="대화">
            {turns.map((t, i) => (
              <li key={i} className="space-y-3">
                <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-paper">{t.q}</p>
                <div className="rounded-2xl rounded-tl-sm border border-line bg-white p-4"><AnswerView a={t.a} showFacts={false} /></div>
              </li>
            ))}
          </ol>
          <div ref={end} />
          <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="sticky bottom-3 flex gap-2 rounded-xl border-2 border-ink bg-white p-2 shadow-[4px_4px_0_var(--color-ink)]">
            <label htmlFor="q" className="sr-only">질문</label>
            <input id="q" value={q} onChange={(e) => setQ(e.target.value)} maxLength={300} placeholder="예: 돌풍이 세면 추천이 바뀌나요?"
              className="min-w-0 flex-1 rounded-lg px-3 py-2 text-base outline-none" />
            <button type="submit" disabled={busy || q.trim().length < 2} className="rounded-lg bg-ink px-4 py-2 font-semibold text-paper disabled:opacity-50">
              {busy ? "답하는 중…" : "묻기"}
            </button>
          </form>
          <p className="text-xs text-ink-2">질문은 1분에 5번까지입니다. 질문과 답은 품질 점검을 위해 저장됩니다.</p>
        </>
      )}
    </div>
  );
}
