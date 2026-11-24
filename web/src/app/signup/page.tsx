"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Message } from "@/lib/types";
import { AuthFrame, Field, Notice, Submit, TextLink, useSubmit } from "@/components/auth/Form";

const pwRule = (pw: string) => pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw);

export default function Signup() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const { busy, error, submit } = useSubmit(
    () => api<Message>("/api/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) }), (r) => setSent(r.message));
  const resend = useSubmit(() => api<Message>("/api/auth/verify-email/resend", { method: "POST", body: JSON.stringify({ email }) }),
    (r) => setSent(r.message));

  if (sent) {
    return (
      <AuthFrame title="메일함을 확인해 주세요" lead={sent}>
        <div className="space-y-4">
          <ol className="list-decimal space-y-1.5 pl-5 text-ink-2">
            <li>{email} 로 온 ‘이메일 주소를 확인해 주세요’ 메일을 엽니다.</li>
            <li>메일의 <b className="text-ink">이메일 확인</b> 버튼을 누릅니다. 링크는 24시간 동안 쓸 수 있습니다.</li>
            <li>확인이 끝나면 로그인합니다.</li>
          </ol>
          {resend.error && <Notice kind="error">{resend.error.message}</Notice>}
          <button type="button" onClick={() => resend.submit()} disabled={resend.busy}
            className="w-full rounded-md border border-ink px-4 py-2.5 font-semibold">인증 메일 다시 보내기</button>
          <p className="text-sm text-ink-2">개발 환경이면 메일은 Mailpit(<code>localhost:8025</code>)에 쌓입니다.</p>
        </div>
      </AuthFrame>
    );
  }
  const weak = password.length > 0 && !pwRule(password);
  return (
    <AuthFrame title="이메일로 가입" lead={<>이미 회원이면 <TextLink href="/login">로그인</TextLink>.</>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="이름" name="name" autoComplete="nickname" required maxLength={40} value={name} onChange={(e) => setName(e.target.value)}
          hint="추천 화면과 메일에 보이는 이름입니다." error={error?.problem.fields?.name} />
        <Field label="이메일" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          error={error?.problem.fields?.email} />
        <Field label="비밀번호" name="password" type="password" autoComplete="new-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} hint="8자 이상, 영문과 숫자를 함께" error={weak ? "8자 이상, 영문과 숫자를 함께 써 주세요." : undefined} />
        {error && !error.problem.fields && <Notice kind="error">{error.message}</Notice>}
        <Submit busy={busy}>가입하고 인증 메일 받기</Submit>
      </form>
    </AuthFrame>
  );
}
