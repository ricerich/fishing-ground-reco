import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans-kr/400.css";
import "@fontsource/ibm-plex-sans-kr/600.css";
import "@fontsource/ibm-plex-sans-kr/700.css";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "어장 추천",
  description: "고등어 · 방어 · 삼치 — 오늘 평소보다 잘 잡힐 권역 Top-3",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e2a3b" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-dvh">
        <AuthProvider>
          <SiteHeader />
          <main className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
