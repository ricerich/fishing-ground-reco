"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Notice, TextLink } from "@/components/auth/Form";

/** 관리자 화면 입구 — 권한 확인만. 수집 · 모델 · 작업 화면은 3단계에서 채운다 */
export default function Admin() {
  const { me, ready } = useAuth();
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    if (!ready) return;
    api("/api/admin/ping").then(() => setStatus(200)).catch((e: ApiError) => setStatus(e.problem.status));
  }, [ready, me]);
  return (
    <div className="mt-8 max-w-2xl space-y-4">
      <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-4xl">관리자</h1>
      {status === null ? <p className="text-ink-2">권한 확인 중…</p>
        : status === 401 ? <Notice kind="error">로그인이 필요합니다. <TextLink href="/login?next=/admin">로그인</TextLink></Notice>
        : status === 403 ? <Notice kind="error">관리자만 볼 수 있는 화면입니다. 관리자는 서버의 ADMIN_EMAILS 에 적힌 이메일을 인증한 회원입니다.</Notice>
        : <Notice kind="ok">{me?.name}님, 관리자 권한을 확인했습니다. 수집 현황 · 모델 교체 기록 · 작업 실행은 다음 단계에서 이 화면에 붙습니다.</Notice>}
    </div>
  );
}
