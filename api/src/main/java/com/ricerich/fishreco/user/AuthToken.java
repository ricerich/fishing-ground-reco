package com.ricerich.fishreco.user;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/** 인증 · 재설정 토큰 — 원문은 메일에만, DB 에는 SHA-256 해시. 1회용 · 만료 */
@Entity
@Table(name = "auth_token")
public class AuthToken {
    public enum Purpose { VERIFY_EMAIL, RESET_PASSWORD }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "token_id")
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Purpose purpose;

    @Column(name = "token_hash", nullable = false)
    private String tokenHash;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "expires_at", nullable = false)
    private LocalDateTime expiresAt;

    @Column(name = "used_at")
    private LocalDateTime usedAt;

    protected AuthToken() {}

    public AuthToken(Long userId, Purpose purpose, String tokenHash, LocalDateTime now, LocalDateTime expiresAt) {
        this.userId = userId;
        this.purpose = purpose;
        this.tokenHash = tokenHash;
        this.createdAt = now;
        this.expiresAt = expiresAt;
    }

    public Long getUserId() { return userId; }
    public Purpose getPurpose() { return purpose; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public boolean usable(LocalDateTime now) { return usedAt == null && expiresAt.isAfter(now); }
    public boolean expired(LocalDateTime now) { return !expiresAt.isAfter(now); }
    public boolean used() { return usedAt != null; }
    public void use(LocalDateTime now) { this.usedAt = now; }
}
