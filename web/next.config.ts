import type { NextConfig } from "next";

// 화면(3000)과 Spring(8080)을 '같은 주소'처럼 보이게 한다 → 세션 쿠키 · CSRF 가 CORS 없이 동작
const API = process.env.API_BASE_URL ?? "http://127.0.0.1:8080";

const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/oauth2/:path*", destination: `${API}/oauth2/:path*` },
      { source: "/login/oauth2/:path*", destination: `${API}/login/oauth2/:path*` },
    ];
  },
};

export default config;
