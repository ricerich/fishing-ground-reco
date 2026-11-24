// RAG 스트림 읽기 — Spring 이 넘겨주는 NDJSON(한 줄 = 이벤트 하나)을 받는 대로 넘긴다
import { ApiError } from "./api";
import type { Problem } from "./types";

export interface Source { id: string; title: string; section: string; kind: string; sample: boolean; text: string }
export interface Check { cited: string[]; made_up: string[]; cite_ok: boolean; said_unknown: boolean; numbers_ok: boolean; unknown_numbers: string[] }
export type RagEvent =
  | { type: "meta"; mode: string; llm: string; sources: Source[]; facts?: string | null }
  | { type: "notice"; text: string }
  | { type: "delta"; text: string }
  | { type: "done"; answer: string; check: Check; llm: string; seconds: number }
  | { type: "logged"; qaId: number };

function csrf() {
  const m = document.cookie.match(/(?:^|; )XSRF-TOKEN=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function streamRag(path: string, body: unknown, on: (e: RagEvent) => void, signal?: AbortSignal) {
  if (!csrf()) await fetch("/api/health", { credentials: "include" });
  const res = await fetch(path, {
    method: "POST", credentials: "include", signal,
    headers: { "Content-Type": "application/json", "X-XSRF-TOKEN": csrf() }, body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let p: Problem = { status: res.status };
    try { p = { ...p, ...(await res.json()) }; } catch { /* 본문 없음 */ }
    throw new ApiError(p);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) on(JSON.parse(line) as RagEvent);
    }
  }
}

export async function sendFeedback(qaId: number, helpful: boolean) {
  const { api } = await import("./api");
  return api(`/api/rag/${qaId}/feedback`, { method: "POST", body: JSON.stringify({ helpful }) });
}

/** 답 글을 조각으로 — 인용 [추천] · [문서#번호] 를 표시용 조각으로 바꾼다 */
export function splitCites(text: string): ({ t: "text"; v: string } | { t: "cite"; v: string })[] {
  const out: ({ t: "text"; v: string } | { t: "cite"; v: string })[] = [];
  const re = /\[([^\[\]\s]+#\d+|추천)\]/g;
  let last = 0, m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ t: "text", v: text.slice(last, m.index) });
    out.push({ t: "cite", v: m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ t: "text", v: text.slice(last) });
  return out;
}
