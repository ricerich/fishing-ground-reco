"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Providers } from "@/lib/types";
import { AuthFrame, Field, Notice, Submit, TextLink, useSubmit } from "@/components/auth/Form";
import { SocialButtons } from "@/components/auth/SocialButtons";

function Login() {
  const router = useRouter();
  const sp = useSearchParams();
  const { refresh } = useAuth();
  const [providers, setProviders] = useState<Providers | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resent, setResent] = useState<string | null>(null);
  const next = sp.get("next") ?? "/";
  useEffect(() => { api<Providers>("/api/auth/providers").then(setProviders).catch(() => setProviders(null)); }, []);

  const done = async () => { await refresh(); router.push(next); };
  const { busy, error, submit } = useSubmit(
    () => api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }), done);
  const demoUser = useSubmit(() => api("/api/auth/demo-login", { method: "POST", body: JSON.stringify({ role: "USER" }) }), done);
  const demoAdmin = useSubmit(() => api("/api/auth/demo-login", { method: "POST", body: JSON.stringify({ role: "ADMIN" }) }), done);
  const resend = useSubmit(() => api<{ message: string }>("/api/auth/verify-email/resend", { method: "POST", body: JSON.stringify({ email }) }),
    (r) => setResent(r.message));

  const fromSocial = sp.get("error");
  return (
    <AuthFrame title="로그인" lead={<>처음이면 <TextLink href="/signup">이메일로 가입</TextLink>하거나 소셜 계정으로 바로 시작하세요.</>}>
      <div className="space-y-5">
        {fromSocial && <Notice kind="error">{fromSocial}</Notice>}
        {sp.get("reset") && <Notice kind="ok">비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요.</Notice>}
        <form onSubmit={submit} className="space-y-4" noValidate>
          <Field label="이메일" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Field label="비밀번호" name="password" type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} />
          {error && (
            <Notice kind="error">
              {error.message}
              {error.problem.code === "email_unverified" && (
                <button type="button" onClick={() => resend.submit()} className="ml-2 font-semibold underline underline-offset-4">인증 메일 다시 보내기</button>
              )}
              {error.problem.code === "locked" && <> <TextLink href="/forgot">비밀번호 재설정</TextLink></>}
            </Notice>
          )}
          {resent && <Notice kind="ok">{resent}</Notice>}
          {resend.error && <Notice kind="error">{resend.error.message}</Notice>}
          <Submit busy={busy}>로그인</Submit>
          <p className="text-right text-sm"><TextLink href="/forgot">비밀번호를 잊으셨나요?</TextLink></p>
        </form>
        <div className="flex items-center gap-3 text-sm text-ink-2"><span className="h-px flex-1 bg-line" />또는<span className="h-px flex-1 bg-line" /></div>
        <SocialButtons providers={providers} />
        {providers?.demoLogin && (
          <div className="rounded-md border border-dashed border-gale bg-gale-soft/60 p-3 text-sm">
            <p className="font-semibold">시연 로그인 <span className="font-normal text-ink-2">— demo 프로필에서만 보입니다</span></p>
            <div className="mt-2 flex gap-2">
              <button type="button" onClick={() => demoUser.submit()} className="rounded border border-ink bg-white px-3 py-1.5">시연 사용자</button>
              <button type="button" onClick={() => demoAdmin.submit()} className="rounded border border-ink bg-white px-3 py-1.5">시연 관리자</button>
            </div>
          </div>
        )}
      </div>
    </AuthFrame>
  );
}

export default function Page() {
  return <Suspense><Login /></Suspense>;
}
