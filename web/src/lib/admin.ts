// 관리자 API 응답 모양 — api/.../admin/AdminController.java (뷰 열을 camelCase 로 그대로)
export interface Gate { id: number; name: string; pass: boolean; detail: string }
export interface SpeciesScore { p: number | null; champ?: number | null; rule?: number | null; days: number }
export interface ModelRow {
  version: string; kind: "rule" | "logistic" | "gbm"; status: "candidate" | "champion" | "rejected" | "retired";
  createdAt: string; fitFrom: string | null; fitUntil: string | null; statsUntil: string | null; evalFrom: string | null; evalUntil: string | null;
  nTrain: number | null; nGroups: number | null; pAt3: number | null; hitAt3: number | null; ndcgAt3: number | null; rulePAt3: number | null;
  champVersion: string | null; champPAt3: number | null; diff: number | null; ciLow: number | null; ciHigh: number | null;
  perSpecies: Record<string, SpeciesScore> | null; gates: Gate[] | null; decision: string | null; promotedAt: string | null; retiredAt: string | null;
}
export interface Promotion { logId: number; at: string; action: string; fromVersion: string | null; toVersion: string | null; actor: string; reason: string | null }
export interface JobRun { runId: number; job: string; triggerBy: string; startedAt: string; endedAt: string | null; status: string; summary: string | null; detail?: Record<string, unknown> }
export interface CollectSource { source: string; lastOk: string | null; n7d: number; ok7d: number; rows24h: number; lastFail: string | null; lastFailNote: string | null }
export interface CollectLog { logId: number; logged: string; source: string; target: string; status: string; nRows: number; seconds: number; note: string | null }
export interface QueueItem { queueId: number; job: string; params: Record<string, unknown>; requestedBy: string; requestedAt: string; status: string; runId: number | null; summary?: string | null; runStatus?: string | null; done?: boolean }
export interface Overview {
  today: string; demo: boolean; champion: ModelRow | null; collect: CollectSource[]; jobs: JobRun[]; lastRetrain: JobRun | null;
  pending: QueueItem[]; promotions: Promotion[]; runnable: Record<string, string>; schedule: { time: string; job: string }[];
}

export const SOURCE: Record<string, string> = { auction: "위판", khoa: "권역 관측", sea_forecast: "해상예보", fishing_index: "낚시지수" };
export const JOB: Record<string, string> = {
  collect_daily: "수집", precompute_today: "오늘 추천 계산", precompute_range: "기간 추천 계산", evaluate_live: "채점",
  retrain_weekly: "재학습 · 교체 판단", rollback: "되돌리기", bootstrap_demo: "시연 초기화", demo_weak_champion: "시연: 약한 챔피언", rag_reindex: "RAG 색인",
};
export const ACTION: Record<string, string> = { promote: "교체", reject: "거절", rollback: "되돌리기", bootstrap: "시작", scenario: "시연 시나리오" };
export const KIND: Record<string, string> = { rule: "규칙(어제 좋았던 곳)", logistic: "로지스틱 회귀", gbm: "그래디언트 부스팅" };
export const STATUS: Record<string, string> = { champion: "챔피언", candidate: "후보", rejected: "거절", retired: "물러남" };

export const n3 = (v: number | null | undefined) => (v == null ? "—" : Number(v).toFixed(3));
export const signed = (v: number | null | undefined) => (v == null ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(Number(v)).toFixed(3)}`);
export const when = (s: string | null | undefined) => (s ? s.slice(5, 16).replace("T", " ").replace("-", "/") : "—");
