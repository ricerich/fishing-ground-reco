package com.ricerich.fishreco.user;

import jakarta.persistence.*;
import java.io.Serializable;
import java.time.LocalDateTime;

/** 관심 품목 · 권역 */
@Entity
@Table(name = "favorite")
@IdClass(Favorite.Key.class)
public class Favorite {
    public record Key(Long userId, String kind, String value) implements Serializable {
        public Key() { this(null, null, null); }
    }

    @Id @Column(name = "user_id") private Long userId;
    @Id private String kind;
    @Id private String value;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    protected Favorite() {}

    public Favorite(Long userId, String kind, String value, LocalDateTime now) {
        this.userId = userId;
        this.kind = kind;
        this.value = value;
        this.createdAt = now;
    }

    public String getKind() { return kind; }
    public String getValue() { return value; }
}
