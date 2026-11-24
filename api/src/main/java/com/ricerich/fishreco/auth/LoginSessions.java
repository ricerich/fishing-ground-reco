package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Component;

/** 로그인 = 세션에 AppPrincipal 넣기. 세션 고정 공격을 막으려고 로그인 순간 세션 ID 를 바꾼다. */
@Component
public class LoginSessions {
    private final SecurityContextRepository repo = new HttpSessionSecurityContextRepository();

    public void login(AppPrincipal p, HttpServletRequest req, HttpServletResponse res) {
        req.getSession(true);
        req.changeSessionId();
        Authentication auth = UsernamePasswordAuthenticationToken.authenticated(p, null, p.authorities());
        SecurityContext ctx = SecurityContextHolder.createEmptyContext();
        ctx.setAuthentication(auth);
        SecurityContextHolder.setContext(ctx);
        repo.saveContext(ctx, req, res);
    }

    public void logout(HttpServletRequest req) {
        SecurityContextHolder.clearContext();
        var s = req.getSession(false);
        if (s != null) s.invalidate();
    }

    public static AppPrincipal current() {
        Authentication a = SecurityContextHolder.getContext().getAuthentication();
        if (a != null && a.getPrincipal() instanceof AppPrincipal p) return p;
        throw new ApiException(org.springframework.http.HttpStatus.UNAUTHORIZED, "login", "로그인이 필요합니다");
    }

    public static AppPrincipal currentOrNull() {
        Authentication a = SecurityContextHolder.getContext().getAuthentication();
        return a != null && a.getPrincipal() instanceof AppPrincipal p ? p : null;
    }
}
