package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.auth.AuthDtos.*;
import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import com.ricerich.fishreco.user.Repositories.IdentityRepo;
import com.ricerich.fishreco.user.Repositories.UserRepo;
import com.ricerich.fishreco.user.User;
import com.ricerich.fishreco.user.UserIdentity;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

/** 이메일 회원 가입 · 인증 · 로그인 · 재설정 (로그아웃은 SecurityConfig 의 /api/auth/logout) */
@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService auth;
    private final LoginSessions sessions;
    private final AppProperties props;
    private final ClientRegistrationRepository clients;
    private final UserRepo users;
    private final IdentityRepo identities;

    public AuthController(AuthService auth, LoginSessions sessions, AppProperties props, ClientRegistrationRepository clients,
                          UserRepo users, IdentityRepo identities) {
        this.auth = auth;
        this.sessions = sessions;
        this.props = props;
        this.clients = clients;
        this.users = users;
        this.identities = identities;
    }

    @PostMapping("/signup")
    @ResponseStatus(HttpStatus.CREATED)
    public Message signup(@Valid @RequestBody SignupReq r) {
        auth.signup(r.email(), r.password(), r.name());
        return new Message(AuthService.normalize(r.email()) + " 로 인증 메일을 보냈습니다. 메일의 버튼을 누르면 가입이 끝납니다.");
    }

    @PostMapping("/verify-email")
    public Message verify(@Valid @RequestBody TokenReq r) {
        User u = auth.verifyEmail(r.token());
        return new Message(u.getDisplayName() + "님, 이메일 확인이 끝났습니다. 이제 로그인할 수 있습니다.");
    }

    @PostMapping("/verify-email/resend")
    public Message resend(@Valid @RequestBody EmailReq r) {
        auth.resendVerification(r.email());
        return new Message("인증을 기다리는 계정이면 메일을 다시 보냈습니다. 받은 편지함과 스팸함을 확인해 주세요.");
    }

    @PostMapping("/login")
    public Map<String, Object> login(@Valid @RequestBody LoginReq r, HttpServletRequest req, HttpServletResponse res) {
        User u = auth.login(r.email(), r.password());
        AppPrincipal p = AppPrincipal.of(u, "email");
        sessions.login(p, req, res);
        return Map.of("name", p.name(), "role", p.role());
    }

    @PostMapping("/password-reset/request")
    public Message resetRequest(@Valid @RequestBody EmailReq r) {
        auth.requestReset(r.email());
        return new Message("가입된 이메일이면 재설정 링크를 보냈습니다. 링크는 30분 동안 쓸 수 있습니다.");
    }

    @PostMapping("/password-reset/confirm")
    public Message resetConfirm(@Valid @RequestBody ResetReq r) {
        auth.confirmReset(r.token(), r.password());
        return new Message("비밀번호를 바꿨습니다. 다른 기기의 로그인은 모두 끊겼습니다. 새 비밀번호로 로그인해 주세요.");
    }

    /** 화면이 소셜 버튼을 켤지 정한다 — 키가 비어 있으면(unset) 그 버튼은 '설정 안 됨' */
    @GetMapping("/providers")
    public Providers providers() {
        return new Providers(configured("kakao"), configured("naver"), configured("google"), props.demoLogin());
    }

    private boolean configured(String id) {
        var c = clients.findByRegistrationId(id);
        return c != null && !"unset".equals(c.getClientId()) && !c.getClientId().isBlank();
    }

    /** demo 프로필 전용 — 실제 키 없이 화면을 찍기 위한 시연 사용자 (운영에서는 app.demo-login=false → 404) */
    @PostMapping("/demo-login")
    @Transactional
    public Map<String, Object> demoLogin(@RequestBody(required = false) Map<String, String> body, HttpServletRequest req,
                                         HttpServletResponse res) {
        if (!props.demoLogin()) throw ApiException.notFound("not_found", "없는 경로입니다");
        boolean admin = body != null && "ADMIN".equals(body.get("role"));
        String key = admin ? "demo-admin" : "demo-user";
        String email = key + "@fishreco.local";
        User u = identities.findByProviderAndProviderUserId("demo", key)
                .flatMap(i -> users.findById(i.getUserId()))
                .orElseGet(() -> {
                    var now = AuthService.now();
                    User n = users.save(new User(email, true, admin ? "시연 관리자" : "시연 사용자", User.Status.ACTIVE, now));
                    identities.save(new UserIdentity(n.getId(), "demo", key, email, now));
                    return n;
                });
        u.setRole(admin ? User.Role.ADMIN : User.Role.USER);
        u.touchLogin(AuthService.now());
        AppPrincipal p = AppPrincipal.of(u, "demo");
        sessions.login(p, req, res);
        return Map.of("name", p.name(), "role", p.role());
    }
}
