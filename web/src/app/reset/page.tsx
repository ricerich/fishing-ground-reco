"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { AuthFrame, Field, Notice, Submit, TextLink, useSubmit } from "@/components/auth/Form";

function Reset() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const mismatch = again.length > 0 && again !== password;
  const { busy, error, submit, setError } = useSubmit(
    () => api("/api/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, password }) }),
    () => router.push("/login?reset=1"));
  return (
    <AuthFrame title="새 비밀번호 정하기" lead="바꾸면 다른 기기의 로그인은 모두 끊깁니다. 링크는 30분 동안, 한 번만 쓸 수 있습니다.">
      {!token ? <Notice kind="error">링크에 확인 값이 없습니다. <TextLink href="/forgot">재설정 메일을 다시 받아 주세요.</TextLink></Notice> : (
        <form onSubmit={(e) => { if (mismatch) { e.preventDefault(); return; } setError(null); submit(e); }} className="space-y-4" noValidate>
          <Field label="새 비밀번호" name="password" type="password" autoComplete="new-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} hint="8자 이상, 영문과 숫자를 함께" />
          <Field label="한 번 더" name="again" type="password" autoComplete="new-password" required value={again}
            onChange={(e) => setAgain(e.target.value)} error={mismatch ? "위와 같게 넣어 주세요." : undefined} />
          {error && <Notice kind="error">{error.message} {["token_used", "token_expired", "token_invalid"].includes(error.problem.code ?? "") && <TextLink href="/forgot">다시 받기</TextLink>}</Notice>}
          <Submit busy={busy}>비밀번호 바꾸기</Submit>
        </form>
      )}
    </AuthFrame>
  );
}

export default function Page() {
  return <Suspense><Reset /></Suspense>;
}
