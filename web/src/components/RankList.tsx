"use client";
import type { Item } from "@/lib/types";
import { weight } from "@/lib/format";

function Facts({ it }: { it: Item }) {
  const f = it.feats ?? {};
  const parts = [
    `평소 ${weight(it.usualKg)}`,
    f.wtem != null ? `어제 수온 ${f.wtem.toFixed(1)}℃` : null,
    f.wtem_anom != null ? `평년보다 ${f.wtem_anom >= 0 ? "+" : ""}${f.wtem_anom.toFixed(1)}℃` : null,
  ].filter(Boolean);
  return <p className="num text-sm text-ink-2">{parts.join(" · ")}</p>;
}

function Warnings({ it }: { it: Item }) {
  if (!it.warnings.length) return null;
  return (
    <ul className="mt-2 space-y-1">
      {it.warnings.map((w) => (
        <li key={w} className="rounded border-l-4 border-gale bg-gale-soft px-2.5 py-1.5 text-sm">{w}</li>
      ))}
    </ul>
  );
}

export function RankList({ items, onExplain, picked, onPick, actions, favorites = [] }: {
  favorites?: string[];
  items: Item[];
  onExplain?: (it: Item) => void;
  picked?: string | null;
  onPick?: (area: string) => void;
  actions?: (it: Item) => React.ReactNode;
}) {
  if (!items.length) return <p className="text-ink-2">추천할 권역이 없습니다.</p>;
  const [first, ...rest] = items;
  return (
    <ol className="space-y-3" aria-label="추천 순위">
      <li className={`rounded-lg border-2 bg-white p-4 ${picked === first.area ? "border-buoy" : "border-ink"}`}
        onMouseEnter={() => onPick?.(first.area)}>
        <div className="flex items-start gap-4">
          <span className="num grid size-12 shrink-0 place-items-center rounded-full bg-buoy text-2xl font-bold text-white">1</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <h2 className="text-2xl font-bold tracking-tight">{first.area}{favorites.includes(first.area) && <span className="ml-2 align-middle rounded-full border border-depth px-2 py-0.5 text-xs font-semibold text-depth">관심 권역</span>}</h2>
              <span className="num text-sm text-ink-2" title="권역끼리 순서를 정하는 값 — 확률로 읽지 않는다">점수 {first.score.toFixed(2)}</span>
            </div>
            <Facts it={first} />
            <ul className="mt-2 space-y-0.5">
              {first.reasons.map((r) => <li key={r}>{r}</li>)}
            </ul>
            <Warnings it={first} />
            <div className="mt-3 flex flex-wrap gap-2">
              {onExplain && (
                <button type="button" onClick={() => onExplain(first)}
                  className="rounded border border-ink px-3 py-1.5 text-sm font-semibold hover:bg-ink hover:text-paper">
                  왜 이 권역인가요?
                </button>
              )}
              {actions?.(first)}
            </div>
          </div>
        </div>
      </li>
      {rest.map((it) => (
        <li key={it.area} className={`rounded-lg border bg-white p-4 ${picked === it.area ? "border-buoy" : "border-line"}`}
          onMouseEnter={() => onPick?.(it.area)}>
          <div className="flex items-start gap-4">
            <span className="num grid size-9 shrink-0 place-items-center rounded-full border-2 border-buoy text-lg font-bold text-buoy">{it.rank}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <h3 className="text-lg font-semibold">{it.area}{favorites.includes(it.area) && <span className="ml-2 align-middle rounded-full border border-depth px-2 py-0.5 text-xs font-semibold text-depth">관심 권역</span>}</h3>
                <span className="num text-sm text-ink-2">점수 {it.score.toFixed(2)}</span>
              </div>
              <Facts it={it} />
              <p className="mt-1 text-sm">{it.reasons.join(" · ")}</p>
              <Warnings it={it} />
              <div className="mt-2 flex flex-wrap gap-2">
                {onExplain && (
                  <button type="button" onClick={() => onExplain(it)} className="text-sm font-semibold text-depth underline underline-offset-4">
                    왜 이 권역인가요?
                  </button>
                )}
                {actions?.(it)}
              </div>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
