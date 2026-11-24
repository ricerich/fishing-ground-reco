"use client";
// 소셜 로그인 버튼 — 제공자 안내에 맞춘 색. 키가 없는 제공자는 '설정 안 됨'으로 눌리지 않게
import type { Providers } from "@/lib/types";

const P = [
  { id: "kakao", label: "카카오로 계속하기", cls: "bg-[#FEE500] text-black/85 border-[#FEE500]" },
  { id: "naver", label: "네이버로 계속하기", cls: "bg-[#03C75A] text-white border-[#03C75A]" },
  { id: "google", label: "구글로 계속하기", cls: "bg-white text-ink border-line" },
] as const;

export function SocialButtons({ providers, hrefFor = (id) => `/oauth2/authorization/${id}` }: {
  providers: Providers | null; hrefFor?: (id: string) => string;
}) {
  return (
    <ul className="space-y-2">
      {P.map((p) => {
        const on = providers?.[p.id] ?? false;
        return (
          <li key={p.id}>
            {on ? (
              <a href={hrefFor(p.id)} className={`flex items-center justify-center rounded-md border px-4 py-2.5 font-semibold ${p.cls}`}>
                {p.label}
              </a>
            ) : (
              <span aria-disabled className="flex items-center justify-center gap-2 rounded-md border border-dashed border-line px-4 py-2.5 text-ink-2/70"
                title=".env 에 이 제공자의 키를 넣으면 켜집니다">
                {p.label.replace("로 계속하기", "")} · 설정 안 됨
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
