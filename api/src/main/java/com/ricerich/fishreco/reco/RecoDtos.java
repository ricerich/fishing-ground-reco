package com.ricerich.fishreco.reco;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** 추천 화면이 받는 모양 — web/src/lib/types.ts 와 같게 유지한다 */
public final class RecoDtos {
    private RecoDtos() {}

    public record Area(int areaId, String name, String station, double lat, double lon) {}

    public record Item(int rank, int areaId, String area, double lat, double lon, double score, int usualKg,
                       List<String> reasons, List<String> warnings, Map<String, Object> feats) {}

    public record Excluded(String area, String reason) {}

    public record Run(String servedVersion, String servedKind, LocalDate dataLastDay, BigDecimal yesterdayFill,
                      int candidates, LocalDateTime computedAt) {}

    public record ModelInfo(String version, String kind, String status, BigDecimal pAt3, BigDecimal rulePAt3,
                            LocalDate evalFrom, LocalDate evalUntil, String decision) {}

    /** 최근 n주 실제 성적 — 서비스한 모델 vs 규칙 vs 무작위 기대값 */
    public record Recent(int weeks, Integer days, BigDecimal served, BigDecimal rule, BigDecimal random) {}

    public record Recommendation(String species, LocalDate date, boolean available, String message, Run run, ModelInfo model,
                                 Recent recent, List<Item> items, List<Item> others, List<Excluded> excluded,
                                 List<String> notes) {}

    public record Meta(LocalDate today, boolean demo, List<String> species, LocalDate firstDate, LocalDate lastDate,
                       boolean demoLogin) {}

    public record HistoryDay(LocalDate date, String servedVersion, BigDecimal servedP, BigDecimal ruleP, BigDecimal randomP,
                             List<String> top3, List<String> goodAreas, int labeled) {}

    public record History(String species, int weeks, Recent summary, List<HistoryDay> days) {}
}
