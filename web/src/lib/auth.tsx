"use client";
// 로그인 상태 한곳 — 머리글 · 마이페이지 · 로그인 화면이 같은 값을 본다
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Me } from "./types";

interface AuthState { me: Me | null; ready: boolean; refresh: () => Promise<Me | null>; logout: () => Promise<void> }
const Ctx = createContext<AuthState>({ me: null, ready: false, refresh: async () => null, logout: async () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const m = await api<Me>("/api/me");
      setMe(m);
      return m;
    } catch (e) {
      if (!(e instanceof ApiError && e.problem.status === 401)) console.warn(e);
      setMe(null);
      return null;
    } finally {
      setReady(true);
    }
  }, []);
  const logout = useCallback(async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    setMe(null);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return <Ctx.Provider value={{ me, ready, refresh, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export const PROVIDER_LABEL: Record<string, string> = { email: "이메일", kakao: "카카오", naver: "네이버", google: "구글", demo: "시연" };
