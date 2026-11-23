"use client";
// 해도 — 권역 14곳을 실제 좌표에 찍고, 오늘의 Top-3 을 번호 붙은 항로점처럼 표시한다 (타일 서버 없이 SVG)
import { geoMercator, geoPath, geoGraticule } from "d3-geo";
import type { Feature, FeatureCollection, MultiPolygon } from "geojson";
import coast from "@/data/coast.json";
import type { Area, Item } from "@/lib/types";

const W = 520;
const H = 640;
// 권역마다 이름표 위치 (바다 쪽으로). 좌표는 조위관측소 — 항구 좌표를 지어내지 않기 위해
const LABEL: Record<string, [number, number, "start" | "end" | "middle"]> = {
  "부산": [12, 14, "start"], "통영·거제": [4, 22, "middle"], "삼천포·남해": [-10, -12, "end"], "마산·진해": [-12, -10, "end"],
  "여수·고흥": [0, 24, "middle"], "완도·강진": [0, 24, "middle"], "목포·신안": [-12, 4, "end"], "제주 북·서": [-14, -6, "end"],
  "제주 남·동": [14, 16, "start"], "울산·경주": [12, 4, "start"], "포항·영덕": [12, 4, "start"], "후포·죽변": [12, 4, "start"],
  "삼척·강릉": [12, 4, "start"], "속초·고성": [12, 4, "start"],
};

const frame: Feature = {
  type: "Feature", properties: {},
  geometry: { type: "MultiPoint", coordinates: [[125.75, 33.05], [130.25, 38.45]] },
};
const projection = geoMercator().fitExtent([[18, 18], [W - 18, H - 18]], frame);
const path = geoPath(projection);
const land = coast as unknown as FeatureCollection<MultiPolygon>;
const grid = geoGraticule().extent([[125, 32], [131, 39]]).step([1, 1])();

export function CoastChart({ areas, items, excluded, topK = 3, onPick, picked }: {
  areas: Area[];
  items: Item[];
  excluded: string[];
  topK?: number;
  onPick?: (area: string) => void;
  picked?: string | null;
}) {
  const byArea = new Map(items.map((i) => [i.area, i]));
  const ex = new Set(excluded);
  return (
    <figure className="overflow-hidden rounded-lg border border-line bg-paper-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img"
        aria-label={`권역 지도 — 1위 ${items[0]?.area ?? "없음"}`}>
        <rect width={W} height={H} fill="var(--color-paper-2)" />
        <path d={path(grid) ?? ""} fill="none" stroke="var(--color-depth)" strokeOpacity={0.22} strokeDasharray="2 4" />
        {land.features.map((f) => (
          <path key={String(f.id)} d={path(f) ?? ""} fill="var(--color-land)" stroke="var(--color-land-edge)" strokeWidth={0.8} />
        ))}
        {[126, 127, 128, 129, 130].map((lon) => {
          const p = projection([lon, 33.05]);
          return p && <text key={lon} x={p[0] + 3} y={H - 6} fontSize={10} fill="var(--color-depth)" paintOrder="stroke" stroke="var(--color-paper-2)" strokeWidth={3}>{lon}°E</text>;
        })}
        {[34, 35, 36, 37, 38].map((lat) => {
          const p = projection([125.75, lat]);
          return p && <text key={lat} x={4} y={p[1] - 3} fontSize={10} fill="var(--color-depth)" paintOrder="stroke" stroke="var(--color-paper-2)" strokeWidth={3}>{lat}°N</text>;
        })}
        {areas.map((a) => {
          const p = projection([a.lon, a.lat]);
          if (!p) return null;
          const it = byArea.get(a.name);
          const top = it && it.rank <= topK;
          const out = ex.has(a.name) || !it;
          const [dx, dy, anchor] = LABEL[a.name] ?? [10, 4, "start"];
          return (
            <g key={a.areaId} transform={`translate(${p[0]},${p[1]})`}
              className={onPick ? "cursor-pointer" : undefined} onClick={() => onPick?.(a.name)}>
              {top ? (
                <>
                  <circle r={picked === a.name ? 16 : 13} fill="var(--color-buoy)" stroke="var(--color-paper)" strokeWidth={2.5} />
                  <text textAnchor="middle" y={5} fontSize={14} fontWeight={700} fill="#fff">{it.rank}</text>
                </>
              ) : out ? (
                <circle r={4.5} fill="var(--color-paper-2)" stroke="var(--color-ink-2)" strokeOpacity={0.5} strokeWidth={1.2} />
              ) : (
                <circle r={5} fill="var(--color-ink)" />
              )}
              <text x={top ? dx * 1.5 : dx} y={dy} textAnchor={anchor} fontSize={top ? 14 : 12}
                fontWeight={top ? 700 : 400} fill={out ? "var(--color-ink-2)" : "var(--color-ink)"}
                fillOpacity={out ? 0.6 : 1} paintOrder="stroke" stroke="var(--color-paper-2)" strokeWidth={3}>
                {a.name}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line px-3 py-2 text-xs text-ink-2">
        <span className="inline-flex items-center gap-1.5"><i className="inline-block size-3 rounded-full bg-buoy" />오늘의 Top-{topK}</span>
        <span className="inline-flex items-center gap-1.5"><i className="inline-block size-2.5 rounded-full bg-ink" />후보 권역</span>
        <span className="inline-flex items-center gap-1.5"><i className="inline-block size-2.5 rounded-full border border-ink-2/60" />철이 아니어서 뺀 권역</span>
        <span className="ml-auto">점 = 권역의 조위관측소 위치</span>
      </figcaption>
    </figure>
  );
}
