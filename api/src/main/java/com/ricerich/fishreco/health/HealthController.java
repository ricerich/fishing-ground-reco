package com.ricerich.fishreco.health;

import com.ricerich.fishreco.ai.AiClient;
import com.ricerich.fishreco.config.Today;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** 네 부분(api · app DB · reco 뷰 · AI 서버)이 각각 살아 있는지 — 0단계 확인 화면과 통합 점검이 쓴다 */
@RestController
public class HealthController {
    private final JdbcClient jdbc;
    private final AiClient ai;
    private final Today today;

    public HealthController(JdbcClient jdbc, AiClient ai, Today today) {
        this.jdbc = jdbc;
        this.ai = ai;
        this.today = today;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("api", "ok");
        out.put("today", today.get());
        out.put("demo", today.demo());
        out.put("appDb", check(() -> jdbc.sql("SELECT COUNT(*) FROM flyway_schema_history").query(Long.class).single() + " migrations"));
        out.put("recoViews", check(() -> jdbc.sql("SELECT COUNT(*) FROM reco.v_svc_area").query(Long.class).single() + " areas"));
        try {
            out.put("ai", ai.health());
        } catch (RuntimeException e) {
            out.put("ai", Map.of("status", "down", "detail", e.getMessage()));
        }
        return out;
    }

    private Object check(java.util.function.Supplier<String> s) {
        try {
            return Map.of("status", "ok", "detail", s.get());
        } catch (RuntimeException e) {
            return Map.of("status", "down", "detail", e.getClass().getSimpleName());
        }
    }
}
