package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.user.User;
import java.io.Serializable;
import java.util.List;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

/** 세션에 담는 '로그인한 사람' — 이메일 로그인 · 소셜 로그인 모두 이 모양 하나로 통일 */
public record AppPrincipal(Long userId, String name, String email, String role, String loginWith, int sessionVersion)
        implements Serializable {

    public static AppPrincipal of(User u, String loginWith) {
        return new AppPrincipal(u.getId(), u.getDisplayName(), u.getEmail(), u.getRole().name(), loginWith, u.getSessionVersion());
    }

    public List<GrantedAuthority> authorities() {
        return role.equals("ADMIN")
                ? List.of(new SimpleGrantedAuthority("ROLE_USER"), new SimpleGrantedAuthority("ROLE_ADMIN"))
                : List.of(new SimpleGrantedAuthority("ROLE_USER"));
    }

    public boolean admin() { return "ADMIN".equals(role); }
}
