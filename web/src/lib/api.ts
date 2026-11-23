// 모든 요청은 같은 주소의 /api (next.config.ts 가 Spring 으로 넘김) — 쿠키 · CSRF 가 그대로 따라간다
import type { Problem } from "./types";

export class ApiError extends Error {
  constructor(public problem: Problem) {
    super(problem.detail ?? `요청 실패 (${problem.status})`);
  }
}

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const m = document.cookie.match(/(?:^|; )XSRF-TOKEN=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : undefined;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (method !== "GET") {
    if (!csrfToken()) await fetch("/api/health", { credentials: "include" }); // 첫 요청이면 쿠키부터 받기
    const t = csrfToken();
    if (t) headers.set("X-XSRF-TOKEN", t);
  }
  const res = await fetch(path, { ...init, method, headers, credentials: "include", cache: "no-store" });
  if (!res.ok) {
    let p: Problem = { status: res.status };
    try {
      p = { ...p, ...(await res.json()) };
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(p);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
