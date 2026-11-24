"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Message } from "@/lib/types";
import { AuthFrame, Notice, TextLink } from "@/components/auth/Form";

function Verify() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null);
  const once = useRef(false);                          // 토큰은 1회용 — 개발 모드의 effect 두 번 실행에도 한 번만 보낸다
  useEffect(() => {
    if (!token || once.current) return;
    once.current = true;
    api<Message>("/api/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) })
      .then((r) => setState({ ok: true, text: r.message }))
      .catch((e: ApiError) => setState({ ok: false, text: e.message }));
  }, [token]);
  return (
    <AuthFrame title="이메일 확인">
      <div className="space-y-4">
        {!token ? <Notice kind="error">링크에 확인 값이 없습니다. 메일의 버튼을 다시 눌러 주세요.</Notice>
          : !state ? <p className="text-ink-2">확인하는 중…</p>
          : <Notice kind={state.ok ? "ok" : "error"}>{state.text}</Notice>}
        {state?.ok && <a href="/login" className="block rounded-md bg-ink px-4 py-3 text-center font-semibold text-paper">로그인하러 가기</a>}
        {state && !state.ok && <p className="text-sm">로그인 화면에서 인증 메일을 다시 받을 수 있습니다. <TextLink href="/login">로그인</TextLink></p>}
      </div>
    </AuthFrame>
  );
}

export default function Page() {
  return <Suspense><Verify /></Suspense>;
}
