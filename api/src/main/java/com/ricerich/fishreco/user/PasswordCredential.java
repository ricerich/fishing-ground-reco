package com.ricerich.fishreco.user;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/** 이메일 로그인 비밀번호 (BCrypt) + 연속 실패 잠금 */
@Entity
@Table(name = "password_credential")
public class PasswordCredential {
    public static final int MAX_FAILS = 5;
    public static final int LOCK_MINUTES = 10;

    @Id
    @Column(name = "user_id")
    private Long userId;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "changed_at", nullable = false)
    private LocalDateTime changedAt;

    @Column(name = "failed_count", nullable = false)
    private int failedCount;

    @Column(name = "locked_until")
    private LocalDateTime lockedUntil;

    protected PasswordCredential() {}

    public PasswordCredential(Long userId, String hash, LocalDateTime now) {
        this.userId = userId;
        this.passwordHash = hash;
        this.changedAt = now;
    }

    public Long getUserId() { return userId; }
    public String getPasswordHash() { return passwordHash; }
    public LocalDateTime getLockedUntil() { return lockedUntil; }

    public boolean locked(LocalDateTime now) { return lockedUntil != null && lockedUntil.isAfter(now); }

    public void fail(LocalDateTime now) {
        failedCount++;
        if (failedCount >= MAX_FAILS) {
            lockedUntil = now.plusMinutes(LOCK_MINUTES);
            failedCount = 0;
        }
    }

    public void success() { failedCount = 0; lockedUntil = null; }

    public void change(String hash, LocalDateTime now) {
        this.passwordHash = hash;
        this.changedAt = now;
        success();
    }
}
