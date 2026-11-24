package com.ricerich.fishreco.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.ricerich.fishreco.common.ApiException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/** 회원 규칙 — 비밀번호 규칙 · 이메일 정규화 · 토큰 해시 */
class AuthRulesTest {

    @ParameterizedTest
    @ValueSource(strings = {"short1", "onlyletters", "12345678", ""})
    void 약한_비밀번호는_거절(String pw) {
        assertThatThrownBy(() -> AuthService.checkPassword(pw)).isInstanceOf(ApiException.class);
    }

    @Test
    void 영문과_숫자를_섞은_8자_이상은_통과() {
        assertThatCode(() -> AuthService.checkPassword("Bada2026sea")).doesNotThrowAnyException();
    }

    @Test
    void 이메일은_앞뒤_공백을_빼고_소문자로() {
        assertThat(AuthService.normalize("  Minsu@Example.TEST ")).isEqualTo("minsu@example.test");
    }

    @Test
    void 토큰은_원문이_아니라_SHA256_해시로_저장() {
        String h = AuthService.sha256("abc");
        assertThat(h).hasSize(64).isEqualTo("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }
}
