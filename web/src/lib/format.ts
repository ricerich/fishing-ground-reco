// 화면 글자 만들기 — 숫자 · 날짜는 여기서만 (테스트: format.test.ts)
const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

/** "2026-10-15" → "10월 15일(목)". 브라우저 시간대와 무관하게 문자열에서 바로 계산 */
export function dayLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const w = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return `${m}월 ${d}일(${WEEK[w]})`;
}

export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
}

/** 1720 → "1.7톤", 756 → "756kg" */
export function weight(kg: number): string {
  if (kg >= 1000) return `${(kg / 1000).toFixed(kg >= 10000 ? 0 : 1)}톤`;
  return `${Math.round(kg).toLocaleString("ko-KR")}kg`;
}

/** 0.6417 → "64%" */
export function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

/** 어제 위판 반영률(평소 대비) → 짧은 설명 */
export function fillNote(v: number | null | undefined): { text: string; low: boolean } {
  if (v == null) return { text: "어제 위판량을 알 수 없음", low: true };
  const p = Math.round(v * 100);
  if (v < 0.5) return { text: `어제 위판이 평소의 ${p}%만 들어옴 — 아직 덜 채워졌을 수 있음`, low: true };
  return { text: `어제 위판이 평소의 ${p}% 들어옴`, low: false };
}

export function modelName(kind: string | null | undefined, version: string): string {
  if (kind === "rule") return "규칙(어제 좋았던 곳)";
  const k = kind === "logistic" ? "로지스틱" : kind === "gbm" ? "GBM" : kind ?? "";
  return `${version} · ${k}`;
}

/** 받침에 맞춘 조사 — josa("여수·고흥", "이", "가") → "여수·고흥이" */
export function josa(word: string, withBatchim: string, without: string) {
  const c = word.charCodeAt(word.length - 1) - 0xac00;
  return word + (c >= 0 && c <= 11171 && c % 28 ? withBatchim : without);
}
