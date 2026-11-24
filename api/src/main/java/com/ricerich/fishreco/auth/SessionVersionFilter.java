package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.user.Repositories.UserRepo;
import com.ricerich.fishreco.user.User;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 세션에 적힌 번호(sessionVersion)가 DB 와 다르면 그 세션을 버린다.
 * 비밀번호 재설정 · 변경 · 탈퇴 → DB 번호 +1 → 다른 기기의 로그인이 다음 요청에서 끊긴다.
 */
public class SessionVersionFilter extends OncePerRequestFilter {
    private final UserRepo users;

    public SessionVersionFilter(UserRepo users) {
        this.users = users;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        AppPrincipal p = LoginSessions.currentOrNull();
        if (p != null) {
            User u = users.findById(p.userId()).orElse(null);
            if (u == null || u.getStatus() == User.Status.DELETED || u.getSessionVersion() != p.sessionVersion()) {
                HttpSession s = req.getSession(false);
                if (s != null) s.invalidate();
                SecurityContextHolder.clearContext();
            }
        }
        chain.doFilter(req, res);
    }
}
