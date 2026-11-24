"use client";
// 주별 P@3 — 보여 드린 추천(부표 주황) · 규칙(파랑) · 무작위 기대값(점선). 한 축, 0~100%.
import { useMemo, useState } from "react";
import type { HistoryDay } from "@/lib/types";
import { pct } from "@/lib/format";

interface Week { start: string; served: number; rule: number; random: number; days: number }

function weekStart(d: string) {
  const t = new Date(d + "T00:00:00");
  t.setDate(t.getDate() - ((t.getDay() + 6) % 7));        // 월요일
  return t.toISOString().slice(0, 10);
}

export function weekly(days: HistoryDay[]): Week[] {
  const m = new Map<string, HistoryDay[]>();
  for (const d of days) {
    const k = weekStart(d.date);
    m.set(k, [...(m.get(k) ?? []), d]);
  }
  const avg = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  return [...m.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([start, ds]) => ({
    start, days: ds.length, served: avg(ds.map((d) => d.servedP)), rule: avg(ds.map((d) => d.ruleP)),
    random: avg(ds.map((d) => d.randomP ?? 0)),
  }));
}

const W = 720, H = 260, L = 44, R = 92, T = 16, B = 30;

export function WeeklyChart({ days }: { days: HistoryDay[] }) {
  const ws = useMemo(() => weekly(days), [days]);
  const [hover, setHover] = useState<number | null>(null);
  if (ws.length < 2) return <p className="text-ink-2">주별로 그리려면 2주 이상의 결과가 필요합니다.</p>;
  const x = (i: number) => L + (i * (W - L - R)) / (ws.length - 1);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const path = (k: "served" | "rule" | "random") => ws.map((w, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(w[k]).toFixed(1)}`).join("");
  const last = ws.length - 1;
  const ends = [
    { k: "served" as const, label: "보여 드린 추천", cls: "text-buoy", v: ws[last].served },
    { k: "rule" as const, label: "규칙", cls: "text-rule", v: ws[last].rule },
    { k: "random" as const, label: "무작위", cls: "text-ink-2", v: ws[last].random },
  ].sort((a, b) => b.v - a.v);
  ends.forEach((e, i) => { (e as typeof e & { ly: number }).ly = Math.max(y(e.v), T + 8 + i * 16); });   // 끝 이름표가 겹치지 않게
  for (let i = 1; i < ends.length; i++) {
    const a = ends[i - 1] as typeof ends[0] & { ly: number }, b = ends[i] as typeof ends[0] & { ly: number };
    if (b.ly - a.ly < 16) b.ly = a.ly + 16;
  }
  const h = hover == null ? null : ws[hover];
  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="주별 Top-3 적중률: 보여 드린 추천, 규칙, 무작위"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          setHover(Math.max(0, Math.min(last, Math.round(((px - L) / (W - L - R)) * last))));
        }}>
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="stroke-line" strokeWidth={v === 0 ? 1 : 0.6} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" className="fill-ink-2 text-[11px]">{v * 100}%</text>
          </g>
        ))}
        {ws.map((w, i) => (i % Math.ceil(ws.length / 8) === 0 || i === last) && (
          <text key={w.start} x={x(i)} y={H - 10} textAnchor="middle" className="fill-ink-2 text-[11px]">{w.start.slice(5).replace("-", "/")}</text>
        ))}
        {h && <line x1={x(hover!)} x2={x(hover!)} y1={T} y2={H - B} className="stroke-ink-2" strokeWidth={1} strokeDasharray="3 3" />}
        <path d={path("random")} fill="none" className="stroke-ink-2" strokeWidth={1.5} strokeDasharray="5 4" />
        <path d={path("rule")} fill="none" className="stroke-rule" strokeWidth={2} />
        <path d={path("served")} fill="none" className="stroke-buoy" strokeWidth={2} />
        {ws.map((w, i) => (
          <g key={w.start}>
            <circle cx={x(i)} cy={y(w.rule)} r={hover === i ? 5 : 3.5} className="fill-rule stroke-white" strokeWidth={1.5} />
            <circle cx={x(i)} cy={y(w.served)} r={hover === i ? 5 : 3.5} className="fill-buoy stroke-white" strokeWidth={1.5} />
          </g>
        ))}
        {ends.map((e) => (
          <text key={e.k} x={W - R + 8} y={(e as typeof e & { ly: number }).ly + 4} className={`fill-current text-[12px] font-semibold ${e.cls}`}>{e.label}</text>
        ))}
      </svg>
      {h && (
        <div className="num pointer-events-none absolute top-2 rounded-md border border-line bg-white px-3 py-2 text-sm shadow-sm"
          style={{ left: `${Math.min(70, (x(hover!) / W) * 100)}%` }}>
          <p className="font-semibold">{h.start.slice(5).replace("-", "/")} 주 · {h.days}일</p>
          <p><span className="text-buoy">●</span> 보여 드린 추천 {pct(h.served)}</p>
          <p><span className="text-rule">●</span> 규칙 {pct(h.rule)}</p>
          <p className="text-ink-2">┄ 무작위 {pct(h.random)}</p>
        </div>
      )}
      <figcaption className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <span><span className="text-buoy">━</span> 보여 드린 추천</span><span><span className="text-rule">━</span> 규칙(어제 좋았던 곳)</span>
        <span>┄ 무작위로 세 곳 골랐을 때 기대값</span><span>· 점 = 그 주 평균 Top-3 적중률(P@3)</span>
      </figcaption>
    </figure>
  );
}
