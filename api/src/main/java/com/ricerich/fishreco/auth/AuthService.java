package com.ricerich.fishreco.auth;

import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import com.ricerich.fishreco.config.Today;
import com.ricerich.fishreco.mail.MailService;
import com.ricerich.fishreco.user.AuthToken;
import com.ricerich.fishreco.user.AuthToken.Purpose;
import com.ricerich.fishreco.user.PasswordCredential;
import com.ricerich.fishreco.user.Repositories.*;
import com.ricerich.fishreco.user.User;
import com.ricerich.fishreco.user.UserIdentity;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 이메일 회원 — 가입 · 인증 메일 · 로그인 · 비밀번호 재설정.
 * 규칙
 * - 인증 메일을 확인하기 전에는 로그인할 수 없다 (PENDING)
 * - 토큰은 원문을 메일로만 보내고 DB 에는 SHA-256 해시만 둔다. 1회용, 인증 24시간 · 재설정 30분
 * - 재설정 요청은 계정이 있든 없든 같은 응답 (가입 여부를 알려 주지 않는다)
 * - 비밀번호 5번 연속 틀리면 10분 잠금
 * - 관리자: ADMIN_EMAILS 에 있고 '검증된' 이메일이면 ADMIN
 */
@Service
public class AuthService {
    public static final Duration VERIFY_TTL = Duration.ofHours(24);
    public static final Duration RESET_TTL = Duration.ofMinutes(30);
    public static final Duration RESEND_GAP = Duration.ofMinutes(1);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final UserRepo users;
    private final IdentityRepo identities;
    private final CredentialRepo credentials;
    private final TokenRepo tokens;
    private final PasswordEncoder encoder;
    private final MailService mail;
    private final AppProperties props;

    public AuthService(UserRepo users, IdentityRepo identities, CredentialRepo credentials, TokenRepo tokens,
                       PasswordEncoder encoder, MailService mail, AppProperties props) {
        this.users = users;
        this.identities = identities;
        this.credentials = credentials;
        this.tokens = tokens;
        this.encoder = encoder;
        this.mail = mail;
        this.props = props;
    }

    static LocalDateTime now() {
        return LocalDateTime.now(Today.SEOUL);
    }

    public static String normalize(String email) {
        return email == null ? null : email.trim().toLowerCase(Locale.ROOT);
    }

    // ── 가입 · 인증 ────────────────────────────────────────────────

    @Transactional
    public void signup(String email, String password, String name) {
        String e = normalize(email);
        if (identities.findByProviderAndProviderUserId("email", e).isPresent()) {
            throw ApiException.conflict("email_taken", "이미 가입된 이메일입니다. 로그인하거나 비밀번호 찾기를 이용해 주세요.");
        }
        checkPassword(password);
        var now = now();
        User u = users.save(new User(e, false, name.trim(), User.Status.PENDING, now));
        identities.save(new UserIdentity(u.getId(), "email", e, e, now));
        credentials.save(new PasswordCredential(u.getId(), encoder.encode(password), now));
        mail.verifyEmail(e, u.getDisplayName(), issue(u.getId(), Purpose.VERIFY_EMAIL, VERIFY_TTL));
    }

    @Transactional
    public void resendVerification(String email) {
        var id = identities.findByProviderAndProviderUserId("email", normalize(email));
        if (id.isEmpty()) return;                                   // 가입 여부를 알려 주지 않는다
        User u = users.findById(id.get().getUserId()).orElseThrow();
        if (u.getStatus() != User.Status.PENDING) return;
        var last = tokens.findFirstByUserIdAndPurposeOrderByCreatedAtDesc(u.getId(), Purpose.VERIFY_EMAIL);
        if (last.isPresent() && last.get().getCreatedAt().plus(RESEND_GAP).isAfter(now())) {
            throw ApiException.tooMany("resend_wait", "인증 메일은 1분에 한 번만 다시 보낼 수 있습니다.");
        }
        tokens.useAll(u.getId(), Purpose.VERIFY_EMAIL, now());       // 예전 링크는 쓸 수 없게
        mail.verifyEmail(u.getEmail(), u.getDisplayName(), issue(u.getId(), Purpose.VERIFY_EMAIL, VERIFY_TTL));
    }

    @Transactional
    public User verifyEmail(String token) {
        AuthToken t = consume(token, Purpose.VERIFY_EMAIL);
        User u = users.findById(t.getUserId()).orElseThrow();
        u.verifyEmail();
        grantAdminIfListed(u);
        return u;
    }

    // ── 로그인 ────────────────────────────────────────────────────

    @Transactional(noRollbackFor = ApiException.class)
    public User login(String email, String password) {
        var bad = new ApiException(HttpStatus.UNAUTHORIZED, "bad_credentials", "이메일 또는 비밀번호가 맞지 않습니다.");
        var id = identities.findByProviderAndProviderUserId("email", normalize(email)).orElseThrow(() -> bad);
        User u = users.findById(id.getUserId()).orElseThrow(() -> bad);
        PasswordCredential c = credentials.findById(u.getId()).orElseThrow(() -> bad);
        var now = now();
        if (c.locked(now)) {
            throw new ApiException(HttpStatus.LOCKED, "locked",
                    "비밀번호를 " + PasswordCredential.MAX_FAILS + "번 틀려 잠시 잠겼습니다. " + PasswordCredential.LOCK_MINUTES + "분 뒤 다시 시도하거나 비밀번호를 재설정하세요.");
        }
        if (!encoder.matches(password, c.getPasswordHash())) {
            c.fail(now);
            throw bad;
        }
        c.success();
        if (u.getStatus() == User.Status.PENDING) {
            throw new ApiException(HttpStatus.FORBIDDEN, "email_unverified", "이메일 인증을 마쳐야 로그인할 수 있습니다. 받은 편지함을 확인해 주세요.");
        }
        if (u.getStatus() == User.Status.DELETED) throw bad;
        grantAdminIfListed(u);
        u.touchLogin(now);
        return u;
    }

    // ── 비밀번호 재설정 · 변경 ─────────────────────────────────────

    @Transactional
    public void requestReset(String email) {
        var id = identities.findByProviderAndProviderUserId("email", normalize(email));
        if (id.isEmpty()) return;                                   // 같은 응답 — 가입 여부를 숨긴다
        User u = users.findById(id.get().getUserId()).orElseThrow();
        if (u.getStatus() == User.Status.DELETED) return;
        tokens.useAll(u.getId(), Purpose.RESET_PASSWORD, now());
        mail.resetPassword(u.getEmail(), u.getDisplayName(), issue(u.getId(), Purpose.RESET_PASSWORD, RESET_TTL));
    }

    @Transactional
    public void confirmReset(String token, String newPassword) {
        checkPassword(newPassword);
        AuthToken t = consume(token, Purpose.RESET_PASSWORD);
        User u = users.findById(t.getUserId()).orElseThrow();
        PasswordCredential c = credentials.findById(u.getId()).orElseThrow();
        c.change(encoder.encode(newPassword), now());
        if (u.getStatus() == User.Status.PENDING) u.verifyEmail();  // 메일을 받았다 = 그 주소의 주인
        u.bumpSessionVersion();                                     // 다른 기기의 로그인을 모두 끊는다
    }

    @Transactional
    public int changePassword(Long userId, String current, String next) {
        PasswordCredential c = credentials.findById(userId)
                .orElseThrow(() -> ApiException.badRequest("no_password", "소셜 로그인만 연결된 계정은 비밀번호가 없습니다."));
        if (!encoder.matches(current, c.getPasswordHash())) {
            throw ApiException.badRequest("bad_current", "지금 비밀번호가 맞지 않습니다.");
        }
        checkPassword(next);
        c.change(encoder.encode(next), now());
        User u = users.findById(userId).orElseThrow();
        u.bumpSessionVersion();
        return u.getSessionVersion();
    }

    // ── 공통 ──────────────────────────────────────────────────────

    public void grantAdminIfListed(User u) {
        if (u.getEmail() != null && u.isEmailVerified() && props.adminEmailSet().contains(normalize(u.getEmail()))) {
            u.setRole(User.Role.ADMIN);
        }
    }

    static void checkPassword(String pw) {
        if (pw == null || pw.length() < 8 || !pw.matches(".*[A-Za-z].*") || !pw.matches(".*\\d.*")) {
            throw ApiException.badRequest("weak_password", "비밀번호는 8자 이상이고 영문과 숫자를 함께 써야 합니다.");
        }
    }

    private String issue(Long userId, Purpose purpose, Duration ttl) {
        byte[] b = new byte[32];
        RANDOM.nextBytes(b);
        String raw = Base64.getUrlEncoder().withoutPadding().encodeToString(b);
        var now = now();
        tokens.save(new AuthToken(userId, purpose, sha256(raw), now, now.plus(ttl)));
        return raw;
    }

    private AuthToken consume(String raw, Purpose purpose) {
        AuthToken t = tokens.findByTokenHash(sha256(raw == null ? "" : raw))
                .filter(x -> x.getPurpose() == purpose)
                .orElseThrow(() -> ApiException.badRequest("token_invalid", "링크가 올바르지 않습니다. 메일의 링크를 그대로 열어 주세요."));
        var now = now();
        if (t.used()) throw ApiException.badRequest("token_used", "이미 사용한 링크입니다.");
        if (t.expired(now)) throw ApiException.badRequest("token_expired", "링크의 유효 시간이 지났습니다. 메일을 다시 받아 주세요.");
        t.use(now);
        return t;
    }

    static String sha256(String s) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
