"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { dayLabel } from "@/lib/format";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "오늘의 추천" },
  { href: "/record", label: "추천 성적" },
  { href: "/ask", label: "물어보기" },
  { href: "/status", label: "시스템 상태" },
];

export function SiteHeader() {
  const path = usePathname();
  const { me, ready, logout } = useAuth();
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    api<Meta>("/api/meta").then(setMeta).catch(() => setMeta(null));
  }, []);
  return (
    <header className="border-b border-line bg-ink text-paper">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-lg font-bold tracking-tight">어장 추천</span>
          <span className="hidden text-sm text-paper/60 sm:inline">고등어 · 방어 · 삼치</span>
        </Link>
        <nav className="flex gap-1 text-sm" aria-label="주 메뉴">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href}
              className={`rounded px-2.5 py-1.5 ${path === n.href ? "bg-paper/15 font-semibold" : "text-paper/75 hover:text-paper"}`}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          {meta?.demo && (
            <span className="rounded border border-gale/60 px-2 py-0.5 text-xs text-gale" title="DEMO_TODAY 로 고정된 날짜">
              시연 자료 · {dayLabel(meta.today)} 기준
            </span>
          )}
          {!ready ? null : me ? (
            <>
              {me.role === "ADMIN" && (
                <Link href="/admin" className={`rounded px-2 py-1 ${path.startsWith("/admin") ? "bg-buoy font-semibold" : "text-paper/80 hover:text-paper"}`}>관리자</Link>
              )}
              <Link href="/me" className={`rounded px-2 py-1 ${path === "/me" ? "bg-paper/15 font-semibold" : "hover:text-paper"}`}>{me.name}님</Link>
              <button type="button" onClick={() => logout()} className="text-paper/70 hover:text-paper">로그아웃</button>
            </>
          ) : (
            <Link href={`/login${path !== "/" && path !== "/login" ? `?next=${encodeURIComponent(path)}` : ""}`}
              className="rounded border border-paper/40 px-3 py-1 font-semibold hover:bg-paper/10">로그인</Link>
          )}
        </div>
      </div>
    </header>
  );
}
