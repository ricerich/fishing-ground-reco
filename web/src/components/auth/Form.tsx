"use client";
// 회원 화면 공통 조각 — 입력칸 · 버튼 · 알림 · 화면 틀
import Link from "next/link";
import { useState } from "react";
import { ApiError } from "@/lib/api";

export function AuthFrame({ title, lead, children, aside }: {
  title: string; lead?: React.ReactNode; children: React.ReactNode; aside?: React.ReactNode;
}) {
  return (
    <div className="mt-8 grid gap-8 lg:mt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-14">
      <div className="order-2 lg:order-1">{aside ?? <MemberAside />}</div>
      <section className="order-1 rounded-lg border border-ink/80 bg-white p-6 shadow-[4px_4px_0_var(--color-ink)] sm:p-8 lg:order-2">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {lead && <p className="mt-1.5 text-ink-2">{lead}</p>}
        <div className="mt-6">{children}</div>
      </section>
    </div>
  );
}

/** 회원이 되면 달라지는 것 — 추천은 로그인 없이도 보인다는 점을 먼저 말한다 */
export function MemberAside() {
  return (
    <div className="max-w-prose space-y-4 text-ink-2">
      <p className="text-lg text-ink">추천은 로그인하지 않아도 볼 수 있습니다.</p>
      <p>회원이 되면 관심 품목과 권역을 저장해 첫 화면에 바로 띄우고, 추천마다 ‘왜 이 권역인가요?’를 물어볼 수 있습니다. 추천이 맞았는지 알려 주시면 성적 채점에 함께 씁니다.</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 border-t border-line pt-4 text-sm">
        <dt className="font-semibold text-ink">이메일</dt><dd>인증 메일을 확인하면 가입이 끝납니다.</dd>
        <dt className="font-semibold text-ink">소셜</dt><dd>카카오 · 네이버 · 구글 계정으로 바로 시작합니다. 같은 이메일이어도 자동으로 합치지 않고, 마이페이지에서 직접 연결합니다.</dd>
      </dl>
    </div>
  );
}

export function Field({ label, hint, error, ...p }: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string; hint?: string; error?: string;
}) {
  const id = p.id ?? p.name;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-semibold">{label}</label>
      <input id={id} {...p} aria-invalid={!!error} aria-describedby={hint || error ? `${id}-help` : undefined}
        className={`block w-full rounded-md border bg-paper/40 px-3 py-2.5 text-base outline-none focus:border-ink focus:bg-white ${error ? "border-buoy" : "border-line"}`} />
      {(error || hint) && <p id={`${id}-help`} className={`text-sm ${error ? "text-buoy" : "text-ink-2"}`}>{error ?? hint}</p>}
    </div>
  );
}

export function Submit({ busy, children }: { busy: boolean; children: React.ReactNode }) {
  return (
    <button type="submit" disabled={busy}
      className="w-full rounded-md bg-ink px-4 py-3 text-base font-semibold text-paper hover:bg-ink-2 disabled:opacity-60">
      {busy ? "처리 중…" : children}
    </button>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "ok"; children: React.ReactNode }) {
  const c = kind === "error" ? "border-buoy bg-buoy-soft" : kind === "ok" ? "border-depth bg-depth-soft" : "border-gale bg-gale-soft";
  return <p role={kind === "error" ? "alert" : "status"} className={`rounded-md border-l-4 px-3 py-2.5 text-sm text-ink ${c}`}>{children}</p>;
}

export function TextLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="font-semibold text-depth underline decoration-depth/40 underline-offset-4 hover:decoration-depth">{children}</Link>;
}

/** 제출 → 서버 메시지 · 칸별 오류 를 한 번에 다루는 작은 훅 */
export function useSubmit<T>(fn: () => Promise<T>, onOk?: (r: T) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      onOk?.(r);
    } catch (x) {
      setError(x instanceof ApiError ? x : new ApiError({ status: 0, detail: "서버에 닿지 못했습니다. 잠시 뒤 다시 시도해 주세요." }));
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, submit, setError };
}
