package com.ricerich.fishreco.config;

import com.ricerich.fishreco.auth.OAuthHandlers;
import com.ricerich.fishreco.auth.SessionVersionFilter;
import com.ricerich.fishreco.user.Repositories.UserRepo;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.logout.HttpStatusReturningLogoutSuccessHandler;
import org.springframework.security.web.context.SecurityContextHolderFilter;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 보안 규칙 한곳 모음
 * - 세션 쿠키(HttpOnly) + CSRF 쿠키(XSRF-TOKEN, 화면이 읽어 X-XSRF-TOKEN 헤더로 돌려보냄)
 * - 공개: 추천 조회 · 회원 가입/로그인 · 소셜 로그인 경로 / 관리자: /api/admin/** 은 ADMIN 만
 * - 로그인 안 한 /api 요청은 화면 이동(302) 대신 401, 권한 부족은 403
 * - 소셜 로그인 성공 · 실패는 OAuthHandlers 가 우리 회원으로 바꿔 처리
 */
@Configuration
public class SecurityConfig {

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    SecurityFilterChain api(HttpSecurity http, OAuthHandlers oauth, UserRepo users) throws Exception {
        var csrfHandler = new CsrfTokenRequestAttributeHandler();
        csrfHandler.setCsrfRequestAttributeName(null);           // 매 요청 토큰을 바로 읽게 (쿠키가 늘 있도록)
        http
            .csrf(c -> c.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()).csrfTokenRequestHandler(csrfHandler))
            .addFilterAfter(new CsrfCookieFilter(), BasicAuthenticationFilter.class)
            .addFilterAfter(new SessionVersionFilter(users), SecurityContextHolderFilter.class)
            .authorizeHttpRequests(a -> a
                .requestMatchers("/api/health", "/actuator/health", "/error").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/meta", "/api/species", "/api/areas", "/api/recommendations",
                                 "/api/recommendations/history").permitAll()
                .requestMatchers("/api/auth/**", "/oauth2/**", "/login/oauth2/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .oauth2Login(o -> o.successHandler(oauth).failureHandler(oauth))
            .logout(l -> l.logoutUrl("/api/auth/logout")
                .logoutSuccessHandler(new HttpStatusReturningLogoutSuccessHandler(HttpStatus.NO_CONTENT))
                .deleteCookies("JSESSIONID"))
            .exceptionHandling(e -> e.authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
            .httpBasic(b -> b.disable())
            .formLogin(f -> f.disable());
        return http.build();
    }

    /** CSRF 토큰을 매 요청 한 번 읽어 XSRF-TOKEN 쿠키가 항상 내려가게 한다 (화면이 첫 POST 전에 쿠키를 갖도록) */
    static final class CsrfCookieFilter extends OncePerRequestFilter {
        @Override
        protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
                throws ServletException, IOException {
            CsrfToken t = (CsrfToken) req.getAttribute(CsrfToken.class.getName());
            if (t != null) t.getToken();
            chain.doFilter(req, res);
        }
    }
}
