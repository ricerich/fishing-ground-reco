"use client";
// 0단계 확인 화면 — 네 부분(화면 · Spring · DB · AI 서버)이 각각 살아 있는지
import { useEffect, useState } from "react";

type Part = { name: string; port: string; ok: boolean | null; detail: string };

export default function StatusPage() {
  const [parts, setParts] = useState<Part[]>([]);
  const [raw, setRaw] = useState<unknown>(null);
  const [at, setAt] = useState<string>("");

  async function check() {
    const list: Part[] = [{ name: "화면 (Next.js)", port: "3000", ok: true, detail: "이 페이지가 보이면 동작 중" }];
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      const h = await res.json();
      setRaw(h);
      list.push({ name: "서비스 서버 (Spring Boot)", port: "8080", ok: h.api === "ok", detail: `오늘 = ${h.today}${h.demo ? " (시연 고정)" : ""}` });
      list.push({ name: "DB app 스키마 (Spring 소유)", port: "3306", ok: h.appDb?.status === "ok", detail: h.appDb?.detail ?? "" });
      list.push({ name: "DB reco 뷰 (파이썬 소유, 읽기만)", port: "3306", ok: h.recoViews?.status === "ok", detail: h.recoViews?.detail ?? "" });
      const ai = h.ai ?? {};
      list.push({
        name: "AI 서버 (FastAPI)", port: "8000", ok: ai.status === "ok",
        detail: ai.status === "ok" ? `챔피언 ${ai.champion} · 위판 자료 ${ai.data_last_day}까지 · RAG ${ai.rag?.ready ? "준비됨" : "준비 안 됨"}` : ai.detail ?? "응답 없음",
      });
    } catch {
      list.push({ name: "서비스 서버 (Spring Boot)", port: "8080", ok: false, detail: "응답 없음 — api 폴더에서 서버를 켜 주세요" });
    }
    setParts(list);
    setAt(new Date().toLocaleTimeString("ko-KR"));
  }

  useEffect(() => { check(); }, []);

  return (
    <div className="mt-6 max-w-3xl space-y-5">
      <h1 className="text-3xl font-bold tracking-tight">시스템 상태</h1>
      <p className="text-ink-2">화면은 Spring 에만 묻고, Spring 이 DB 와 AI 서버의 상태를 모아 알려 줍니다.</p>
      <table className="w-full overflow-hidden rounded-lg border border-line bg-white text-left">
        <thead className="bg-paper-2 text-sm text-ink-2">
          <tr><th className="px-4 py-2">부분</th><th className="px-2">포트</th><th className="px-2">상태</th><th className="px-4">내용</th></tr>
        </thead>
        <tbody>
          {parts.map((p) => (
            <tr key={p.name} className="border-t border-line">
              <td className="px-4 py-3 font-semibold">{p.name}</td>
              <td className="num px-2">{p.port}</td>
              <td className="px-2">
                <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-sm font-semibold ${p.ok ? "bg-depth-soft text-depth" : "bg-buoy-soft text-buoy"}`}>
                  <i className={`inline-block size-2 rounded-full ${p.ok ? "bg-depth" : "bg-buoy"}`} />{p.ok ? "정상" : "확인 필요"}
                </span>
              </td>
              <td className="px-4 text-sm">{p.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-3 text-sm text-ink-2">
        <button type="button" onClick={check} className="rounded border border-ink px-3 py-1.5 font-semibold text-ink hover:bg-ink hover:text-paper">다시 확인</button>
        <span>마지막 확인 {at}</span>
      </div>
      <details className="rounded-lg border border-line bg-white p-4 text-sm">
        <summary className="cursor-pointer font-semibold">GET /api/health 응답 원문</summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(raw, null, 2)}</pre>
      </details>
    </div>
  );
}
