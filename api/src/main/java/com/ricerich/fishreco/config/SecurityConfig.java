package com.ricerich.fishreco.config;

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
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 1단계: 공개 조회만 연다. 회원 · 소셜 로그인 규칙은 2단계에서 이 파일에 더한다.
 * - 세션 쿠키(HttpOnly) + CSRF 쿠키(XSRF-TOKEN, 화면이 읽어 X-XSRF-TOKEN 헤더로 돌려보냄)
 * - 로그인 안 한 /api 요청은 화면 이동(302) 대신 401
 */
@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain api(HttpSecurity http) throws Exception {
        var csrfHandler = new CsrfTokenRequestAttributeHandler();
        csrfHandler.setCsrfRequestAttributeName(null);           // 매 요청 토큰을 바로 읽게 (쿠키가 늘 있도록)
        http
            .csrf(c -> c.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()).csrfTokenRequestHandler(csrfHandler))
            .addFilterAfter(new CsrfCookieFilter(), BasicAuthenticationFilter.class)
            .authorizeHttpRequests(a -> a
                .requestMatchers("/api/health", "/actuator/health", "/error").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/meta", "/api/species", "/api/areas", "/api/recommendations",
                                 "/api/recommendations/history").permitAll()
                .anyRequest().authenticated())
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
