package com.ricerich.fishreco.user;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/** 로그인 수단 하나. (provider, providerUserId) 는 전체에서 하나 → 남의 계정에 붙일 수 없다 */
@Entity
@Table(name = "user_identity")
public class UserIdentity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "identity_id")
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(nullable = false)
    private String provider;

    @Column(name = "provider_user_id", nullable = false)
    private String providerUserId;

    @Column(name = "provider_email")
    private String providerEmail;

    @Column(name = "linked_at", nullable = false)
    private LocalDateTime linkedAt;

    protected UserIdentity() {}

    public UserIdentity(Long userId, String provider, String providerUserId, String providerEmail, LocalDateTime now) {
        this.userId = userId;
        this.provider = provider;
        this.providerUserId = providerUserId;
        this.providerEmail = providerEmail;
        this.linkedAt = now;
    }

    public Long getId() { return id; }
    public Long getUserId() { return userId; }
    public String getProvider() { return provider; }
    public String getProviderUserId() { return providerUserId; }
    public String getProviderEmail() { return providerEmail; }
    public LocalDateTime getLinkedAt() { return linkedAt; }
}
