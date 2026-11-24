"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Message } from "@/lib/types";
import { AuthFrame, Field, Notice, Submit, TextLink, useSubmit } from "@/components/auth/Form";

export default function Forgot() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const { busy, error, submit } = useSubmit(
    () => api<Message>("/api/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) }), (r) => setSent(r.message));
  return (
    <AuthFrame title="비밀번호 재설정" lead="가입한 이메일을 넣으면 새 비밀번호를 정하는 링크를 보내 드립니다.">
      {sent ? (
        <div className="space-y-4">
          <Notice kind="ok">{sent}</Notice>
          <p className="text-sm text-ink-2">가입 여부는 알려 드리지 않습니다. 메일이 오지 않으면 주소를 확인하고 다시 요청해 주세요.</p>
          <TextLink href="/login">로그인으로 돌아가기</TextLink>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <Field label="이메일" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          {error && <Notice kind="error">{error.message}</Notice>}
          <Submit busy={busy}>재설정 링크 받기</Submit>
          <p className="text-sm text-ink-2">소셜 계정으로만 가입했다면 비밀번호가 없습니다. 그 계정으로 로그인해 주세요.</p>
        </form>
      )}
    </AuthFrame>
  );
}
