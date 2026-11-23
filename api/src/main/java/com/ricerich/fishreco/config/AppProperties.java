package com.ricerich.fishreco.config;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** application.properties 의 app.* 값 */
@ConfigurationProperties("app")
public record AppProperties(Ai ai, String demoToday, String webBaseUrl, String adminEmails, boolean demoLogin,
                            Mail mail, Rag rag) {

    public record Ai(String baseUrl, String internalToken, int timeoutSeconds) {}

    public record Mail(String from) {}

    public record Rag(int perMinute) {}

    /** ADMIN_EMAILS (쉼표 구분) → 소문자 집합 */
    public Set<String> adminEmailSet() {
        if (adminEmails == null || adminEmails.isBlank()) return Set.of();
        return Arrays.stream(adminEmails.split(",")).map(String::trim).map(String::toLowerCase)
                .filter(s -> !s.isEmpty()).collect(Collectors.toUnmodifiableSet());
    }
}
