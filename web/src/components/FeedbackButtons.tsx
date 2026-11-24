"use client";
// 추천 카드의 '도움이 됐어요 / 아니에요' — 회원만. 다시 누르면 바뀐다 (한 사람 · 하루 · 품목 · 권역에 한 줄)
import { api } from "@/lib/api";

export type FeedbackMap = Record<string, boolean>;

export function FeedbackButtons({ date, species, area, value, onChange }: {
  date: string; species: string; area: string; value: boolean | undefined; onChange: (area: string, v: boolean) => void;
}) {
  const send = (v: boolean) => api("/api/feedback", { method: "PUT", body: JSON.stringify({ date, species, area, helpful: v }) })
    .then(() => onChange(area, v)).catch(() => undefined);
  const cls = (on: boolean) => `rounded border px-2.5 py-1 text-sm ${on ? "border-ink bg-ink text-paper" : "border-line hover:border-ink"}`;
  return (
    <span className="inline-flex items-center gap-1.5" role="group" aria-label={`${area} 추천 평가`}>
      <button type="button" aria-pressed={value === true} onClick={() => send(true)} className={cls(value === true)}>도움이 됐어요</button>
      <button type="button" aria-pressed={value === false} onClick={() => send(false)} className={cls(value === false)}>아니에요</button>
    </span>
  );
}
