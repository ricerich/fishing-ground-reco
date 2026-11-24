package com.ricerich.fishreco.user;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/** 회원 한 사람 — 로그인 수단(이메일 · 카카오 · 네이버 · 구글)은 UserIdentity 로 여러 개 */
@Entity
@Table(name = "users")
public class User {
    public enum Role { USER, ADMIN }

    public enum Status { PENDING, ACTIVE, DELETED }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "user_id")
    private Long id;

    private String email;

    @Column(name = "email_verified", nullable = false)
    private boolean emailVerified;

    @Column(name = "display_name", nullable = false)
    private String displayName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role = Role.USER;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Status status = Status.ACTIVE;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "last_login_at")
    private LocalDateTime lastLoginAt;

    @Column(name = "session_version", nullable = false)
    private int sessionVersion;

    protected User() {}

    public User(String email, boolean emailVerified, String displayName, Status status, LocalDateTime now) {
        this.email = email;
        this.emailVerified = emailVerified;
        this.displayName = displayName;
        this.status = status;
        this.createdAt = now;
    }

    public Long getId() { return id; }
    public String getEmail() { return email; }
    public boolean isEmailVerified() { return emailVerified; }
    public String getDisplayName() { return displayName; }
    public Role getRole() { return role; }
    public Status getStatus() { return status; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getLastLoginAt() { return lastLoginAt; }
    public int getSessionVersion() { return sessionVersion; }

    public void verifyEmail() { this.emailVerified = true; if (status == Status.PENDING) status = Status.ACTIVE; }
    public void setRole(Role role) { this.role = role; }
    public void setEmail(String email, boolean verified) { this.email = email; this.emailVerified = verified; }
    public void touchLogin(LocalDateTime now) { this.lastLoginAt = now; }
    /** 다른 세션을 모두 끊는다 (재설정 · 비밀번호 변경 · 탈퇴) */
    public void bumpSessionVersion() { this.sessionVersion++; }

    public void delete() {
        this.status = Status.DELETED;
        this.email = null;
        this.emailVerified = false;
        this.displayName = "탈퇴한 사용자";
        this.role = Role.USER;
        bumpSessionVersion();
    }
}
