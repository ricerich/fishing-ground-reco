// 교체 조건 5개 — 통과 ✓ / 미달 ✕ 와 숫자. 조건 3 은 '차이와 95% 구간'을 작은 그림으로
import type { Gate, ModelRow } from "@/lib/admin";
import { signed } from "@/lib/admin";

export function DiffBar({ diff, lo, hi, min = 0.01 }: { diff: number; lo: number; hi: number; min?: number }) {
  const left = Math.min(-0.05, lo - 0.01), right = Math.max(0.05, hi + 0.01);
  const x = (v: number) => ((v - left) / (right - left)) * 100;
  const ok = diff >= min && lo > 0;
  return (
    <figure className="mt-2" aria-label={`후보 − 챔피언 ${signed(diff)}, 95% 구간 ${signed(lo)} ~ ${signed(hi)}`}>
      <svg viewBox="0 0 100 18" preserveAspectRatio="none" className="h-7 w-full overflow-visible">
        <rect x={x(0)} y="2" width={x(right) - x(0)} height="14" className="fill-depth-soft/60" />
        <line x1={x(0)} x2={x(0)} y1="0" y2="18" className="stroke-ink" strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
        <line x1={x(min)} x2={x(min)} y1="0" y2="18" className="stroke-depth" strokeDasharray="2 2" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <line x1={x(lo)} x2={x(hi)} y1="9" y2="9" className={ok ? "stroke-buoy" : "stroke-ink-2"} strokeWidth="3" vectorEffect="non-scaling-stroke" />
        <circle cx={x(diff)} cy="9" r="2.2" className={ok ? "fill-buoy" : "fill-ink"} />
      </svg>
      <figcaption className="num flex justify-between text-[11px] text-ink-2">
        <span>{signed(left)}</span>
        <span>0 · 점선 = 기준 +{min.toFixed(2)} · 색 칠한 쪽 = 후보가 나음</span>
        <span>{signed(right)}</span>
      </figcaption>
    </figure>
  );
}

export function Gates({ m }: { m: ModelRow }) {
  if (!m.gates) return <p className="text-sm text-ink-2">이 버전은 교체 조건으로 판단한 기록이 없습니다 (시작 모델 · 규칙 · 같은 회차의 다른 후보).</p>;
  return (
    <ol className="space-y-2">
      {m.gates.map((g: Gate) => (
        <li key={g.id} className={`rounded-md border-l-4 px-3 py-2 ${g.pass ? "border-depth bg-depth-soft/40" : "border-buoy bg-buoy-soft/60"}`}>
          <div className="flex items-baseline gap-2">
            <span aria-hidden className={`text-lg font-bold ${g.pass ? "text-depth" : "text-buoy"}`}>{g.pass ? "✓" : "✕"}</span>
            <span className="font-semibold">{g.id}. {g.name}</span>
            <span className="sr-only">{g.pass ? "통과" : "미달"}</span>
          </div>
          <p className="num ml-6 text-sm text-ink-2">{g.detail}</p>
          {g.id === 3 && m.diff != null && m.ciLow != null && m.ciHigh != null && (
            <div className="ml-6"><DiffBar diff={Number(m.diff)} lo={Number(m.ciLow)} hi={Number(m.ciHigh)} /></div>
          )}
        </li>
      ))}
    </ol>
  );
}
