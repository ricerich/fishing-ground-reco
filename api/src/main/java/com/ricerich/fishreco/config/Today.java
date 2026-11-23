package com.ricerich.fishreco.config;

import java.time.LocalDate;
import java.time.ZoneId;
import org.springframework.stereotype.Component;

/** 서비스의 '오늘'. DEMO_TODAY 가 있으면 그 날 (캡처 · 수업에서 늘 같은 화면) — AI 서버와 같은 규칙. */
@Component
public class Today {
    public static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    private final LocalDate fixed;

    public Today(AppProperties props) {
        String d = props.demoToday();
        this.fixed = (d == null || d.isBlank()) ? null : LocalDate.parse(d.trim());
    }

    public LocalDate get() {
        return fixed != null ? fixed : LocalDate.now(SEOUL);
    }

    public boolean demo() {
        return fixed != null;
    }
}
