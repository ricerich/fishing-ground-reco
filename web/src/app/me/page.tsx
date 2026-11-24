"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { PROVIDER_LABEL, useAuth } from "@/lib/auth";
import type { Area, Me, Message, Providers } from "@/lib/types";
import { Field, Notice, TextLink, useSubmit } from "@/components/auth/Form";

const SOCIAL = ["kakao", "naver", "google"] as const;
const SPECIES = ["고등어", "방어", "삼치"];
/** 받침에 맞춘 조사 — 카카오를 · 구글을 */
const eul = (w: string) => { const c = w.charCodeAt(w.length - 1) - 0xac00; return w + (c >= 0 && c % 28 ? "을" : "를"); };
const day = (s: string) => s.slice(0, 10).replaceAll("-", ".");

function Section({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) {
  return (
    <section className="border-t-2 border-ink pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold">{title}</h2>
        {note && <p className="text-sm text-ink-2">{note}</p>}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Identities({ me, providers, onChange }: { me: Me; providers: Providers | null; onChange: (m: Me) => void }) {
  const [err, setErr] = useState<string | null>(null);
  const linked = new Map(me.identities.map((i) => [i.provider, i]));
  const only = me.identities.length <= 1;
  const unlink = async (p: string) => {
    setErr(null);
    try { onChange(await api<Me>(`/api/me/identities/${p}`, { method: "DELETE" })); } catch (e) { setErr((e as ApiError).message); }
  };
  const rows = [...(linked.has("email") ? ["email"] : []), ...(linked.has("demo") ? ["demo"] : []), ...SOCIAL];
  return (
    <div className="space-y-3">
      {err && <Notice kind="error">{err}</Notice>}
      <ul className="divide-y divide-line rounded-lg border border-line bg-white">
        {rows.map((p) => {
          const i = linked.get(p);
          const social = (SOCIAL as readonly string[]).includes(p);
          const on = social ? providers?.[p as (typeof SOCIAL)[number]] : true;
          return (
            <li key={p} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
              <span className="w-16 font-semibold">{PROVIDER_LABEL[p]}</span>
              <span className="min-w-0 flex-1 text-sm text-ink-2">
                {i ? <>{i.email ?? "이메일 제공 안 함"} · {day(i.linkedAt)} 연결{me.loginWith === p && <b className="ml-2 rounded bg-depth-soft px-1.5 py-0.5 text-xs text-ink">지금 이걸로 로그인</b>}</>
                  : on ? "연결 안 됨" : "설정 안 됨 — .env 에 키를 넣으면 켜집니다"}
              </span>
              {social && (i ? (
                <button type="button" onClick={() => unlink(p)} disabled={only}
                  title={only ? "로그인 수단이 하나뿐이면 해제할 수 없습니다" : undefined}
                  className="rounded border border-line px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50">해제</button>
              ) : on ? (
                <a href={`/api/me/link/${p}`} className="rounded border border-ink bg-ink px-3 py-1.5 text-sm font-semibold text-paper">연결</a>
              ) : null)}
            </li>
          );
        })}
      </ul>
      <p className="text-sm text-ink-2">연결해 두면 어느 수단으로 로그인해도 같은 회원입니다. 같은 이메일을 쓰는 소셜 계정이라도 여기서 직접 연결해야 합쳐집니다.</p>
    </div>
  );
}

function Favorites({ me, onChange }: { me: Me; onChange: (m: Me) => void }) {
  const [areas, setAreas] = useState<Area[]>([]);
  const [sp, setSp] = useState<string[]>(me.favoriteSpecies);
  const [ar, setAr] = useState<string[]>(me.favoriteAreas);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api<Area[]>("/api/areas").then(setAreas).catch(() => setAreas([])); }, []);
  const toggle = (list: string[], set: (v: string[]) => void, v: string) => { setSaved(false); set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]); };
  const { busy, error, submit } = useSubmit(
    () => api<Me>("/api/me/favorites", { method: "PUT", body: JSON.stringify({ species: sp, areas: ar }) }), (m) => { onChange(m); setSaved(true); });
  const chip = (on: boolean) => `rounded-full border px-3 py-1.5 text-sm ${on ? "border-ink bg-ink text-paper" : "border-line bg-white hover:border-ink"}`;
  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-sm font-semibold">품목 — 첫 번째로 고른 품목이 첫 화면에 먼저 뜹니다</legend>
        <div className="flex flex-wrap gap-2">
          {SPECIES.map((s) => <button key={s} type="button" aria-pressed={sp.includes(s)} onClick={() => toggle(sp, setSp, s)} className={chip(sp.includes(s))}>{s}</button>)}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 text-sm font-semibold">권역 — 추천에 들면 표시합니다</legend>
        <div className="flex flex-wrap gap-2">
          {areas.map((a) => <button key={a.areaId} type="button" aria-pressed={ar.includes(a.name)} onClick={() => toggle(ar, setAr, a.name)} className={chip(ar.includes(a.name))}>{a.name}</button>)}
        </div>
      </fieldset>
      {error && <Notice kind="error">{error.message}</Notice>}
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => submit()} disabled={busy} className="rounded-md bg-ink px-4 py-2 font-semibold text-paper disabled:opacity-60">관심 목록 저장</button>
        {saved && <span role="status" className="text-sm text-depth">저장했습니다</span>}
      </div>
    </div>
  );
}

function Password() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const { busy, error, submit } = useSubmit(
    () => api<Message>("/api/me/password", { method: "PUT", body: JSON.stringify({ current, next }) }),
    (r) => { setMsg(r.message); setCurrent(""); setNext(""); });
  return (
    <form onSubmit={submit} className="grid max-w-xl gap-4 sm:grid-cols-2" noValidate>
      <Field label="지금 비밀번호" name="current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      <Field label="새 비밀번호" name="next" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} hint="8자 이상, 영문과 숫자" />
      <div className="space-y-3 sm:col-span-2">
        {error && <Notice kind="error">{error.message}</Notice>}
        {msg && <Notice kind="ok">{msg}</Notice>}
        <button type="submit" disabled={busy} className="rounded-md border border-ink px-4 py-2 font-semibold">비밀번호 바꾸기</button>
      </div>
    </form>
  );
}

function Leave({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(false);
  const { busy, error, submit } = useSubmit(() => api("/api/me", { method: "DELETE" }), onDone);
  return step ? (
    <div className="space-y-3 rounded-lg border-2 border-buoy bg-buoy-soft/50 p-4">
      <p>탈퇴하면 연결된 로그인 수단과 관심 목록이 지워지고, 같은 이메일로 다시 가입하기 전에는 되돌릴 수 없습니다.</p>
      {error && <Notice kind="error">{error.message}</Notice>}
      <div className="flex gap-2">
        <button type="button" onClick={() => submit()} disabled={busy} className="rounded-md bg-buoy px-4 py-2 font-semibold text-white">탈퇴하기</button>
        <button type="button" onClick={() => setStep(false)} className="rounded-md border border-ink px-4 py-2">그만두기</button>
      </div>
    </div>
  ) : (
    <button type="button" onClick={() => setStep(true)} className="text-sm text-ink-2 underline underline-offset-4">회원 탈퇴</button>
  );
}

function MyPage() {
  const { me, ready, refresh } = useAuth();
  const [view, setView] = useState<Me | null>(null);
  const [providers, setProviders] = useState<Providers | null>(null);
  const router = useRouter();
  const sp = useSearchParams();
  useEffect(() => { api<Providers>("/api/auth/providers").then(setProviders).catch(() => setProviders(null)); }, []);
  useEffect(() => { if (ready && !me) router.replace("/login?next=/me"); }, [ready, me, router]);
  const m = view ?? me;
  if (!m) return <p className="mt-8 text-ink-2">불러오는 중…</p>;
  const update = (x: Me) => { setView(x); refresh(); };
  const welcome = sp.get("welcome"), linked = sp.get("linked"), linkErr = sp.get("link_error");
  return (
    <div className="mt-8 max-w-4xl space-y-8">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-4xl">{m.name}님의 마이페이지</h1>
        <p className="mt-1 text-ink-2">
          {m.email ?? "이메일 없음"}{m.email && (m.emailVerified ? " · 확인된 이메일" : " · 확인 전")} · {day(m.createdAt)} 가입
          {m.role === "ADMIN" && <span className="ml-2 rounded bg-buoy px-2 py-0.5 text-sm font-semibold text-white">관리자</span>}
        </p>
      </div>
      {welcome && <Notice kind="ok">{PROVIDER_LABEL[welcome]} 계정으로 가입했습니다. 이미 이메일로 가입한 적이 있다면, 그 계정으로 로그인한 뒤 여기서 {eul(PROVIDER_LABEL[welcome])} 연결하면 하나로 쓸 수 있습니다.</Notice>}
      {linked && <Notice kind="ok">{PROVIDER_LABEL[linked]} 계정을 연결했습니다. 이제 {PROVIDER_LABEL[linked]}로 로그인해도 이 계정입니다.</Notice>}
      {linkErr && <Notice kind="error">{linkErr}</Notice>}
      <Section title="로그인 수단" note={`${m.identities.length}개 연결`}><Identities me={m} providers={providers} onChange={update} /></Section>
      <Section title="관심 품목 · 권역"><Favorites me={m} onChange={update} /></Section>
      {m.hasPassword && <Section title="비밀번호" note="바꾸면 다른 기기의 로그인은 끊깁니다"><Password /></Section>}
      {!m.hasPassword && m.loginWith !== "demo" && (
        <Section title="비밀번호"><p className="text-ink-2">소셜 로그인만 연결된 계정이라 비밀번호가 없습니다. 비밀번호를 쓰려면 <TextLink href="/signup">이메일로 따로 가입</TextLink>해야 합니다.</p></Section>
      )}
      <div className="border-t border-line pt-4"><Leave onDone={async () => { await refresh(); router.replace("/"); }} /></div>
    </div>
  );
}

export default function Page() {
  return <Suspense><MyPage /></Suspense>;
}
