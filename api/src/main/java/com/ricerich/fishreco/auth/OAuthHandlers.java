package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

/**
 * 소셜 로그인이 끝난 뒤 — 제공자 응답을 우리 회원으로 바꾸고(로그인 또는 연결), 세션의 주인을 AppPrincipal 로 바꿔 넣는다.
 * 그래서 앱 전체가 '이메일로 로그인했든 소셜이든' 같은 모양(AppPrincipal)만 보면 된다.
 */
@Component
public class OAuthHandlers implements AuthenticationSuccessHandler, AuthenticationFailureHandler {
    /** 마이페이지에서 연결을 시작한 사람(AppPrincipal) — 제공자에 다녀오는 동안 세션에 적어 둔다 */
    public static final String LINK_ATTR = "LINK_FROM";
    private static final Logger log = LoggerFactory.getLogger(OAuthHandlers.class);
    private final SocialAccounts social;
    private final LoginSessions sessions;
    private final AppProperties props;

    public OAuthHandlers(SocialAccounts social, LoginSessions sessions, AppProperties props) {
        this.social = social;
        this.sessions = sessions;
        this.props = props;
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest req, HttpServletResponse res, Authentication authentication) throws IOException {
        var token = (OAuth2AuthenticationToken) authentication;
        String provider = token.getAuthorizedClientRegistrationId();
        HttpSession s = req.getSession(false);
        AppPrincipal from = s == null ? null : (AppPrincipal) s.getAttribute(LINK_ATTR);
        Long linkUser = from == null ? null : from.userId();
        if (s != null) s.removeAttribute(LINK_ATTR);
        String web = props.webBaseUrl();
        try {
            var profile = SocialAccounts.profile(provider, token.getPrincipal().getAttributes());
            var result = social.handle(profile, linkUser);
            switch (result) {
                case SocialAccounts.Linked l -> {
                    sessions.login(AppPrincipal.of(l.user(), from.loginWith()), req, res);
                    res.sendRedirect(web + "/me?linked=" + provider);
                }
                case SocialAccounts.LoggedIn li -> {
                    sessions.login(AppPrincipal.of(li.user(), provider), req, res);
                    res.sendRedirect(web + (li.created() ? "/me?welcome=" + provider : "/"));
                }
            }
        } catch (ApiException e) {
            log.info("소셜 {} 처리 거절: {}", provider, e.getMessage());
            String q = URLEncoder.encode(e.getMessage(), StandardCharsets.UTF_8);
            // 이 순간 세션의 주인은 Spring 이 넣은 '제공자 토큰'이다 → 연결 실패면 원래 사람으로 되돌리고, 로그인 실패면 비운다
            if (from != null) sessions.login(from, req, res);
            else sessions.logout(req);
            res.sendRedirect(web + (linkUser != null ? "/me?link_error=" + q : "/login?error=" + q));
        }
    }

    @Override
    public void onAuthenticationFailure(HttpServletRequest req, HttpServletResponse res, AuthenticationException e) throws IOException {
        log.info("소셜 로그인 실패: {}", e.getMessage());
        HttpSession s = req.getSession(false);
        boolean linking = s != null && s.getAttribute(LINK_ATTR) != null;
        if (s != null) s.removeAttribute(LINK_ATTR);
        String q = URLEncoder.encode(linking ? "연결을 마치지 못했습니다. 다시 시도해 주세요." : "소셜 로그인에 실패했습니다. 다시 시도해 주세요.",
                StandardCharsets.UTF_8);
        res.sendRedirect(props.webBaseUrl() + (linking ? "/me?link_error=" : "/login?error=") + q);
    }
}
