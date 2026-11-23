// 지도 바탕(해안선) 만들기 — Natural Earth 1:50m (world-atlas 패키지)에서 한반도 · 일본 일부만 잘라 src/data/coast.json 으로
// 타일 서버 없이 그리는 이유: 강의실 · 캡처에서 인터넷이 없어도 늘 같은 지도가 나오게.  실행: npm run coast
import { readFileSync, writeFileSync } from "node:fs";
import { feature } from "topojson-client";

const topo = JSON.parse(readFileSync(new URL("../node_modules/world-atlas/countries-50m.json", import.meta.url)));
const all = feature(topo, topo.objects.countries);
const keep = new Set(["410", "408", "392"]); // 대한민국 · 북한 · 일본
const [W, S, E, N] = [124.3, 32.6, 131.2, 38.9];
const round = (c) => [Math.round(c[0] * 1000) / 1000, Math.round(c[1] * 1000) / 1000];
const inBox = (ring) => ring.some(([x, y]) => x >= W - 1 && x <= E + 1 && y >= S - 1 && y <= N + 1);
const features = all.features
  .filter((f) => keep.has(String(f.id)))
  .map((f) => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    const kept = polys.filter((p) => inBox(p[0])).map((p) => p.map((r) => r.map(round)));
    return { type: "Feature", id: String(f.id), properties: { name: f.properties.name }, geometry: { type: "MultiPolygon", coordinates: kept } };
  })
  .filter((f) => f.geometry.coordinates.length);
const out = { type: "FeatureCollection", bbox: [W, S, E, N], source: "Natural Earth 1:50m via world-atlas@2", features };
writeFileSync(new URL("../src/data/coast.json", import.meta.url), JSON.stringify(out));
console.log(`coast.json: ${features.length} features`);
