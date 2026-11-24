package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.user.Repositories.IdentityRepo;
import com.ricerich.fishreco.user.Repositories.UserRepo;
import com.ricerich.fishreco.user.User;
import com.ricerich.fishreco.user.UserIdentity;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 소셜 로그인 · 연결 — 제공자마다 다른 사용자 정보 모양을 하나(Profile)로 맞춘 뒤 처리한다.
 * - 같은 이메일이어도 자동으로 합치지 않는다 (PRD 결정 1). 처음이면 그 제공자 전용 회원을 만든다
 * - 연결: 로그인한 사람이 마이페이지에서 시작한 경우만. 다른 회원에게 이미 붙은 소셜 계정은 거부
 */
@Service
public class SocialAccounts {

    /** 제공자 응답을 맞춘 모양. emailVerified = 제공자가 '확인된 이메일'이라고 알려 준 경우만 true */
    public record Profile(String provider, String id, String email, boolean emailVerified, String name) {}

    public sealed interface Result permits LoggedIn, Linked {}

    public record LoggedIn(User user, boolean created) implements Result {}

    public record Linked(User user, String provider) implements Result {}

    private final UserRepo users;
    private final IdentityRepo identities;
    private final AuthService auth;

    public SocialAccounts(UserRepo users, IdentityRepo identities, AuthService auth) {
        this.users = users;
        this.identities = identities;
        this.auth = auth;
    }

    @SuppressWarnings("unchecked")
    public static Profile profile(String provider, Map<String, Object> a) {
        return switch (provider) {
            case "google" -> new Profile("google", String.valueOf(a.get("sub")), str(a.get("email")),
                    Boolean.TRUE.equals(a.get("email_verified")), firstNonBlank(str(a.get("name")), "구글 사용자"));
            case "kakao" -> {
                var acc = (Map<String, Object>) a.getOrDefault("kakao_account", Map.of());
                var prof = (Map<String, Object>) acc.getOrDefault("profile", Map.of());
                boolean verified = Boolean.TRUE.equals(acc.get("is_email_valid")) && Boolean.TRUE.equals(acc.get("is_email_verified"));
                yield new Profile("kakao", String.valueOf(a.get("id")), str(acc.get("email")), verified,
                        firstNonBlank(str(prof.get("nickname")), "카카오 사용자"));
            }
            case "naver" -> {
                var r = (Map<String, Object>) a.getOrDefault("response", a);   // 네이버는 response 안에 담아 준다
                yield new Profile("naver", String.valueOf(r.get("id")), str(r.get("email")), false,
                        firstNonBlank(str(r.get("name")), str(r.get("nickname")), "네이버 사용자"));
            }
            default -> throw ApiException.badRequest("provider", "지원하지 않는 로그인: " + provider);
        };
    }

    /** linkUserId 가 있으면 그 회원에 연결, 없으면 로그인(처음이면 가입) */
    @Transactional
    public Result handle(Profile p, Long linkUserId) {
        var now = AuthService.now();
        var existing = identities.findByProviderAndProviderUserId(p.provider(), p.id());
        if (linkUserId != null) {
            if (existing.isPresent()) {
                if (existing.get().getUserId().equals(linkUserId)) return new Linked(users.findById(linkUserId).orElseThrow(), p.provider());
                throw ApiException.conflict("identity_taken", label(p.provider()) + " 계정이 이미 다른 회원에 연결되어 있습니다.");
            }
            if (identities.findByUserIdAndProvider(linkUserId, p.provider()).isPresent()) {
                throw ApiException.conflict("provider_linked", "이미 다른 " + label(p.provider()) + " 계정이 연결되어 있습니다. 먼저 해제해 주세요.");
            }
            identities.save(new UserIdentity(linkUserId, p.provider(), p.id(), AuthService.normalize(p.email()), now));
            User u = users.findById(linkUserId).orElseThrow();
            if (u.getEmail() == null && p.email() != null) u.setEmail(AuthService.normalize(p.email()), p.emailVerified());
            auth.grantAdminIfListed(u);
            return new Linked(u, p.provider());
        }
        if (existing.isPresent()) {
            User u = users.findById(existing.get().getUserId()).orElseThrow();
            if (u.getStatus() == User.Status.DELETED) throw ApiException.badRequest("deleted", "탈퇴한 계정입니다.");
            auth.grantAdminIfListed(u);
            u.touchLogin(now);
            return new LoggedIn(u, false);
        }
        User u = users.save(new User(AuthService.normalize(p.email()), p.emailVerified(), p.name(), User.Status.ACTIVE, now));
        identities.save(new UserIdentity(u.getId(), p.provider(), p.id(), AuthService.normalize(p.email()), now));
        auth.grantAdminIfListed(u);
        u.touchLogin(now);
        return new LoggedIn(u, true);
    }

    public static String label(String provider) {
        return switch (provider) {
            case "kakao" -> "카카오";
            case "naver" -> "네이버";
            case "google" -> "구글";
            default -> "이메일";
        };
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static String firstNonBlank(String... s) {
        for (String x : s) if (x != null && !x.isBlank()) return x;
        return null;
    }
}
