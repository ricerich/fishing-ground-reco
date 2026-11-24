package com.ricerich.fishreco.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.ricerich.fishreco.common.ApiException;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** 제공자마다 다른 사용자 정보 → 하나의 Profile 로 맞추기 (서버 없이 도는 순수 단위 테스트) */
class SocialProfileTest {

    @Test
    void 카카오_이메일은_유효하고_인증된_경우만_검증된_이메일() {
        var a = Map.<String, Object>of("id", 41001L, "kakao_account", Map.of(
                "email", "Sea@Example.test", "is_email_valid", true, "is_email_verified", true,
                "profile", Map.of("nickname", "바다사랑")));
        var p = SocialAccounts.profile("kakao", a);
        assertThat(p.id()).isEqualTo("41001");
        assertThat(p.emailVerified()).isTrue();
        assertThat(p.name()).isEqualTo("바다사랑");

        var noMail = SocialAccounts.profile("kakao", Map.of("id", 7, "kakao_account", Map.of()));
        assertThat(noMail.email()).isNull();
        assertThat(noMail.emailVerified()).isFalse();
        assertThat(noMail.name()).isEqualTo("카카오 사용자");
    }

    @Test
    void 네이버는_response_안을_읽고_이메일을_검증된_것으로_보지_않는다() {
        var p = SocialAccounts.profile("naver", Map.of("resultcode", "00",
                "response", Map.of("id", "nv-1", "nickname", "선장", "email", "c@example.test")));
        assertThat(p.id()).isEqualTo("nv-1");
        assertThat(p.name()).isEqualTo("선장");
        assertThat(p.emailVerified()).isFalse();   // 관리자 권한 판단에 쓰지 않도록
    }

    @Test
    void 구글은_sub_와_email_verified() {
        var p = SocialAccounts.profile("google", Map.of("sub", "g-9", "email", "g@example.test", "email_verified", true, "name", "구글맨"));
        assertThat(p.id()).isEqualTo("g-9");
        assertThat(p.emailVerified()).isTrue();
    }

    @Test
    void 모르는_제공자는_거절() {
        assertThatThrownBy(() -> SocialAccounts.profile("github", Map.of())).isInstanceOf(ApiException.class);
    }
}
