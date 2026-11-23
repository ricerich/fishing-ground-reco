"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { dayLabel } from "@/lib/format";

const NAV = [
  { href: "/", label: "오늘의 추천" },
  { href: "/record", label: "추천 성적" },
  { href: "/status", label: "시스템 상태" },
];

export function SiteHeader() {
  const path = usePathname();
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
        {meta?.demo && (
          <span className="ml-auto rounded border border-gale/60 px-2 py-0.5 text-xs text-gale" title="DEMO_TODAY 로 고정된 날짜">
            시연 자료 · {dayLabel(meta.today)} 기준
          </span>
        )}
      </div>
    </header>
  );
}
