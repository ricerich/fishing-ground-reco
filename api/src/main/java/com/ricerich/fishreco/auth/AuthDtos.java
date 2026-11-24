package com.ricerich.fishreco.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;
import java.util.List;

public final class AuthDtos {
    private AuthDtos() {}

    public record SignupReq(@NotBlank(message = "이메일을 입력해 주세요") @Email(message = "이메일 형식이 아닙니다") String email,
                            @NotBlank(message = "비밀번호를 입력해 주세요") String password,
                            @NotBlank(message = "이름(별명)을 입력해 주세요") @Size(max = 30, message = "30자 이내") String name) {}

    public record LoginReq(@NotBlank(message = "이메일을 입력해 주세요") String email,
                           @NotBlank(message = "비밀번호를 입력해 주세요") String password) {}

    public record EmailReq(@NotBlank(message = "이메일을 입력해 주세요") @Email(message = "이메일 형식이 아닙니다") String email) {}

    public record TokenReq(@NotBlank String token) {}

    public record ResetReq(@NotBlank String token, @NotBlank(message = "새 비밀번호를 입력해 주세요") String password) {}

    public record PasswordChangeReq(@NotBlank(message = "지금 비밀번호를 입력해 주세요") String current,
                                    @NotBlank(message = "새 비밀번호를 입력해 주세요") String next) {}

    public record Message(String message) {}

    public record Identity(String provider, String label, String email, LocalDateTime linkedAt) {}

    public record Me(Long id, String name, String email, boolean emailVerified, String role, String loginWith,
                     boolean hasPassword, List<Identity> identities, List<String> favoriteSpecies, List<String> favoriteAreas,
                     LocalDateTime createdAt) {}

    public record Providers(boolean kakao, boolean naver, boolean google, boolean demoLogin) {}

    public record FavoritesReq(List<String> species, List<String> areas) {}
}
