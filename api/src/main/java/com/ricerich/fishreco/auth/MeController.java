package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.auth.AuthDtos.*;
import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.reco.RecoController;
import com.ricerich.fishreco.user.Favorite;
import com.ricerich.fishreco.user.Repositories.*;
import com.ricerich.fishreco.user.User;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

/** 마이페이지 — 내 정보 · 로그인 수단 연결/해제 · 관심 품목/권역 · 비밀번호 변경 · 탈퇴 */
@RestController
@RequestMapping("/api/me")
public class MeController {
    static final Set<String> SOCIAL = Set.of("kakao", "naver", "google");
    private final UserRepo users;
    private final IdentityRepo identities;
    private final CredentialRepo credentials;
    private final FavoriteRepo favorites;
    private final AuthService auth;
    private final LoginSessions sessions;
    private final JdbcClient jdbc;

    public MeController(UserRepo users, IdentityRepo identities, CredentialRepo credentials, FavoriteRepo favorites,
                        AuthService auth, LoginSessions sessions, JdbcClient jdbc) {
        this.users = users;
        this.identities = identities;
        this.credentials = credentials;
        this.favorites = favorites;
        this.auth = auth;
        this.sessions = sessions;
        this.jdbc = jdbc;
    }

    @GetMapping
    @Transactional(readOnly = true)
    public Me me() {
        AppPrincipal p = LoginSessions.current();
        User u = users.findById(p.userId()).orElseThrow();
        var ids = identities.findByUserIdOrderByLinkedAt(u.getId()).stream()
                .map(i -> new Identity(i.getProvider(), SocialAccounts.label(i.getProvider()), i.getProviderEmail(), i.getLinkedAt()))
                .toList();
        var fav = favorites.findByUserId(u.getId());
        return new Me(u.getId(), u.getDisplayName(), u.getEmail(), u.isEmailVerified(), u.getRole().name(), p.loginWith(),
                credentials.existsById(u.getId()), ids,
                fav.stream().filter(f -> f.getKind().equals("species")).map(Favorite::getValue).toList(),
                fav.stream().filter(f -> f.getKind().equals("area")).map(Favorite::getValue).toList(), u.getCreatedAt());
    }

    @PutMapping("/favorites")
    @Transactional
    public Me saveFavorites(@RequestBody FavoritesReq r) {
        AppPrincipal p = LoginSessions.current();
        List<String> sp = r.species() == null ? List.of() : r.species();
        List<String> ar = r.areas() == null ? List.of() : r.areas();
        if (!RecoController.SPECIES.containsAll(sp)) throw ApiException.badRequest("species", "품목은 " + RecoController.SPECIES + " 중에서");
        var known = jdbc.sql("SELECT area_name FROM reco.v_svc_area").query(String.class).list();
        if (!known.containsAll(ar)) throw ApiException.badRequest("area", "없는 권역이 있습니다");
        favorites.deleteByUserId(p.userId());
        favorites.flush();
        var now = AuthService.now();
        sp.stream().distinct().forEach(s -> favorites.save(new Favorite(p.userId(), "species", s, now)));
        ar.stream().distinct().forEach(a -> favorites.save(new Favorite(p.userId(), "area", a, now)));
        return me();
    }

    /** 연결 시작 — 세션에 '누구에게 붙일지' 적고 제공자 로그인 화면으로 보낸다 (화면 주소 그대로 유지하려고 상대 경로) */
    @GetMapping("/link/{provider}")
    public void linkStart(@PathVariable String provider, HttpServletRequest req, HttpServletResponse res) throws java.io.IOException {
        AppPrincipal p = LoginSessions.current();
        if (!SOCIAL.contains(provider)) throw ApiException.badRequest("provider", "연결할 수 있는 것: 카카오 · 네이버 · 구글");
        req.getSession().setAttribute(OAuthHandlers.LINK_ATTR, p);
        res.sendRedirect("/oauth2/authorization/" + provider);
    }

    @DeleteMapping("/identities/{provider}")
    @Transactional
    public Me unlink(@PathVariable String provider) {
        AppPrincipal p = LoginSessions.current();
        if (!SOCIAL.contains(provider)) throw ApiException.badRequest("provider", "해제할 수 있는 것: 카카오 · 네이버 · 구글");
        var id = identities.findByUserIdAndProvider(p.userId(), provider)
                .orElseThrow(() -> ApiException.notFound("not_linked", SocialAccounts.label(provider) + " 계정이 연결되어 있지 않습니다."));
        if (identities.countByUserId(p.userId()) <= 1) {
            throw ApiException.conflict("last_identity", "로그인 수단이 하나만 남아 해제할 수 없습니다. 다른 수단을 먼저 연결해 주세요.");
        }
        identities.delete(id);
        return me();
    }

    @PutMapping("/password")
    public Message changePassword(@Valid @RequestBody PasswordChangeReq r, HttpServletRequest req, HttpServletResponse res) {
        AppPrincipal p = LoginSessions.current();
        int v = auth.changePassword(p.userId(), r.current(), r.next());
        // 이 기기는 로그인을 유지 — 새 번호로 세션을 다시 만든다 (다른 기기만 끊긴다)
        sessions.login(new AppPrincipal(p.userId(), p.name(), p.email(), p.role(), p.loginWith(), v), req, res);
        return new Message("비밀번호를 바꿨습니다. 다른 기기의 로그인은 끊겼습니다.");
    }

    @DeleteMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void delete(HttpServletRequest req) {
        AppPrincipal p = LoginSessions.current();
        User u = users.findById(p.userId()).orElseThrow();
        identities.deleteByUserId(u.getId());
        credentials.deleteById(u.getId());
        favorites.deleteByUserId(u.getId());
        u.delete();
        var s = req.getSession(false);
        if (s != null) s.invalidate();
    }
}
