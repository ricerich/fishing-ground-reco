"use client";
// '왜 이 권역인가요?' — 추천 표의 숫자 + 서비스 설명 문서로 LLM 이 풀어 쓴다 (회원 기능)
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { streamRag } from "@/lib/rag";
import { josa } from "@/lib/format";
import { AnswerView, emptyAnswer, reduceAnswer, type AnswerState } from "./Answer";

export function ExplainPanel({ species, date, area, rank, onClose }: { species: string; date: string; area: string; rank: number; onClose: () => void }) {
  const { me, ready } = useAuth();
  const [a, setA] = useState<AnswerState>(emptyAnswer());
  const box = useRef<HTMLElement>(null);
  useEffect(() => { box.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [area]);
  useEffect(() => {
    if (!ready || !me) return;
    const ctl = new AbortController();
    setA(emptyAnswer());
    streamRag("/api/rag/explain", { species, date, area }, (e) => setA((x) => reduceAnswer(x, e)), ctl.signal)
      .catch((e) => { if (e.name !== "AbortError") setA((x) => ({ ...x, done: true, error: (e as ApiError).message })); });
    return () => ctl.abort();
  }, [species, date, area, me, ready]);

  return (
    <section ref={box} aria-label={`${area} 추천 설명`} className="scroll-mt-4 rounded-lg border-2 border-ink bg-white p-4 shadow-[4px_4px_0_var(--color-ink)] sm:p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <h2 className="text-lg font-bold">왜 {josa(area, "이", "가")} {rank}위인가요?</h2>
        <button type="button" onClick={onClose} className="rounded px-2 text-ink-2 hover:text-ink" aria-label="설명 닫기">닫기</button>
      </div>
      {!ready ? null : !me ? (
        <p>설명은 회원에게 보여 드립니다. <Link href="/login?next=/" className="font-semibold text-depth underline underline-offset-4">로그인</Link>하면 숫자 근거와 함께 풀어 드립니다.</p>
      ) : <AnswerView a={a} />}
    </section>
  );
}
