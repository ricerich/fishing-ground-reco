// Spring 응답 모양 — api/src/main/java/com/ricerich/fishreco/reco/RecoDtos.java 와 같게 유지
export type Species = "고등어" | "방어" | "삼치";

export interface Feats {
  rel_lag1?: number | null;
  rel_mean7?: number | null;
  sold_days7?: number | null;
  days_since_sale?: number | null;
  wtem?: number | null;
  wtem_anom?: number | null;
  gust_lag1?: number | null;
}

export interface Item {
  rank: number;
  areaId: number;
  area: string;
  lat: number;
  lon: number;
  score: number;
  usualKg: number;
  reasons: string[];
  warnings: string[];
  feats: Feats;
}

export interface Run {
  servedVersion: string;
  servedKind: string | null;
  dataLastDay: string;
  yesterdayFill: number | null;
  candidates: number;
  computedAt: string;
}

export interface ModelInfo {
  version: string;
  kind: string;
  status: string;
  pAt3: number | null;
  rulePAt3: number | null;
  evalFrom: string | null;
  evalUntil: string | null;
  decision: string | null;
}

export interface Recent {
  weeks: number;
  days: number | null;
  served: number | null;
  rule: number | null;
  random: number | null;
}

export interface Recommendation {
  species: Species;
  date: string;
  available: boolean;
  message: string | null;
  run: Run | null;
  model: ModelInfo | null;
  recent: Recent | null;
  items: Item[];
  others: Item[];
  excluded: { area: string; reason: string }[];
  notes: string[];
}

export interface Area {
  areaId: number;
  name: string;
  station: string;
  lat: number;
  lon: number;
}

export interface Meta {
  today: string;
  demo: boolean;
  species: Species[];
  firstDate: string | null;
  lastDate: string | null;
  demoLogin: boolean;
}

export interface HistoryDay {
  date: string;
  servedVersion: string;
  servedP: number;
  ruleP: number;
  randomP: number | null;
  top3: string[];
  goodAreas: string[];
  labeled: number;
}

export interface History {
  species: Species;
  weeks: number;
  summary: Recent;
  days: HistoryDay[];
}

export interface Problem {
  status: number;
  detail?: string;
  code?: string;
  fields?: Record<string, string>;
}
