"use client";
// 관리자 화면 틀 — 권한 확인(401 · 403) 과 하위 메뉴
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Notice, TextLink } from "@/components/auth/Form";

const TABS = [
  { href: "/admin", label: "개요" },
  { href: "/admin/models", label: "모델 · 교체" },
  { href: "/admin/collect", label: "수집" },
  { href: "/admin/jobs", label: "작업 기록" },
  { href: "/admin/usage", label: "이용 기록" },
];

export function AdminShell({ title, lead, children }: { title: string; lead?: string; children: React.ReactNode }) {
  const path = usePathname();
  const { me, ready } = useAuth();
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    if (!ready) return;
    api("/api/admin/ping").then(() => setStatus(200)).catch((e: ApiError) => setStatus(e.problem.status));
  }, [ready, me]);

  return (
    <div className="mt-6 space-y-6">
      <nav aria-label="관리자 메뉴" className="flex flex-wrap gap-1 border-b-2 border-ink">
        {TABS.map((t) => {
          const on = t.href === "/admin" ? path === "/admin" : path.startsWith(t.href);
          return (
            <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}
              className={`-mb-0.5 rounded-t-md border-2 px-4 py-2 text-sm font-semibold ${on ? "border-ink border-b-paper bg-paper" : "border-transparent text-ink-2 hover:text-ink"}`}>
              {t.label}
            </Link>
          );
        })}
      </nav>
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-3xl">{title}</h1>
        {lead && <p className="mt-1 max-w-3xl text-ink-2">{lead}</p>}
      </div>
      {status === null ? <p className="text-ink-2">권한 확인 중…</p>
        : status === 401 ? <Notice kind="error">로그인이 필요합니다. <TextLink href={`/login?next=${path}`}>로그인</TextLink></Notice>
        : status === 403 ? <Notice kind="error">관리자만 볼 수 있는 화면입니다. 관리자는 서버의 ADMIN_EMAILS 에 적힌 이메일을 인증한 회원입니다.</Notice>
        : children}
    </div>
  );
}

export function Panel({ title, note, children, className = "" }: { title: string; note?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-line bg-white p-4 sm:p-5 ${className}`}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-bold">{title}</h2>
        {note && <div className="text-sm text-ink-2">{note}</div>}
      </div>
      {children}
    </section>
  );
}

const TONE: Record<string, string> = {
  champion: "bg-buoy text-white", candidate: "bg-gale-soft text-ink", rejected: "bg-paper-2 text-ink-2 line-through decoration-ink-2/50",
  retired: "bg-paper-2 text-ink-2", ok: "bg-depth-soft text-ink", done: "bg-depth-soft text-ink", fail: "bg-buoy-soft text-buoy",
  running: "bg-gale-soft text-ink", queued: "bg-gale-soft text-ink", skipped: "bg-paper-2 text-ink-2",
  성공: "bg-depth-soft text-ink", 늘어남: "bg-depth-soft text-ink", 재생: "bg-depth-soft text-ink", 있음: "bg-paper-2 text-ink-2",
  없음: "bg-paper-2 text-ink-2", 실패: "bg-buoy text-white",
  promote: "bg-buoy text-white", reject: "bg-paper-2 text-ink-2", rollback: "bg-ink text-paper", bootstrap: "bg-depth-soft text-ink", scenario: "bg-gale text-ink",
};

export function Chip({ k, children }: { k: string; children?: React.ReactNode }) {
  return <span className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold ${TONE[k] ?? "bg-paper-2"}`}>{children ?? k}</span>;
}
