package com.ricerich.fishreco.user;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

/** 회원 관련 저장소 모음 — 이름만 보고 쿼리를 만드는 메서드(쿼리 메서드) 위주 */
public final class Repositories {
    private Repositories() {}

    public interface UserRepo extends JpaRepository<User, Long> {}

    public interface IdentityRepo extends JpaRepository<UserIdentity, Long> {
        Optional<UserIdentity> findByProviderAndProviderUserId(String provider, String providerUserId);
        List<UserIdentity> findByUserIdOrderByLinkedAt(Long userId);
        Optional<UserIdentity> findByUserIdAndProvider(Long userId, String provider);
        long countByUserId(Long userId);
        void deleteByUserId(Long userId);
    }

    public interface CredentialRepo extends JpaRepository<PasswordCredential, Long> {}

    public interface TokenRepo extends JpaRepository<AuthToken, Long> {
        Optional<AuthToken> findByTokenHash(String hash);
        Optional<AuthToken> findFirstByUserIdAndPurposeOrderByCreatedAtDesc(Long userId, AuthToken.Purpose purpose);

        @Modifying
        @Query("update AuthToken t set t.usedAt = :now where t.userId = :userId and t.purpose = :purpose and t.usedAt is null")
        int useAll(Long userId, AuthToken.Purpose purpose, LocalDateTime now);
    }

    public interface FavoriteRepo extends JpaRepository<Favorite, Favorite.Key> {
        List<Favorite> findByUserId(Long userId);
        void deleteByUserId(Long userId);
    }
}
