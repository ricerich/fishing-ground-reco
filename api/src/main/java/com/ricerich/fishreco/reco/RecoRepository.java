package com.ricerich.fishreco.reco;

import com.ricerich.fishreco.reco.RecoDtos.*;
import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

/** reco 스키마의 v_svc_* 뷰만 읽는다 (쓰기 권한 없음). 표 구조가 바뀌어도 뷰 이름 · 열 이름은 약속. */
@Repository
public class RecoRepository {
    private static final TypeReference<List<String>> STRINGS = new TypeReference<>() {};
    private static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() {};
    private final JdbcClient jdbc;
    private final ObjectMapper json;

    public RecoRepository(JdbcClient jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public List<Area> areas() {
        return jdbc.sql("SELECT area_id, area_name, station_name, lat, lon FROM reco.v_svc_area ORDER BY area_id")
                .query((rs, i) -> new Area(rs.getInt(1), rs.getString(2), rs.getString(3), rs.getDouble(4), rs.getDouble(5)))
                .list();
    }

    public Optional<Run> run(String species, LocalDate date) {
        return jdbc.sql("""
                SELECT served_version, served_kind, data_last_day, yesterday_fill, candidates, computed_at
                FROM reco.v_svc_rec_run WHERE rec_date = ? AND species = ?""")
                .params(date, species)
                .query((rs, i) -> new Run(rs.getString(1), rs.getString(2), rs.getObject(3, LocalDate.class),
                        rs.getBigDecimal(4), rs.getInt(5), rs.getTimestamp(6).toLocalDateTime()))
                .optional();
    }

    public List<Item> items(String species, LocalDate date) {
        return jdbc.sql("""
                SELECT rnk, area_id, area_name, lat, lon, score, usual_kg, reasons, warnings, feats
                FROM reco.v_svc_rec WHERE rec_date = ? AND species = ? ORDER BY rnk""")
                .params(date, species).query(this::item).list();
    }

    private Item item(ResultSet rs, int i) throws SQLException {
        return new Item(rs.getInt(1), rs.getInt(2), rs.getString(3), rs.getDouble(4), rs.getDouble(5), rs.getDouble(6),
                rs.getInt(7), strings(rs.getString(8)), strings(rs.getString(9)), map(rs.getString(10)));
    }

    public List<Excluded> excluded(String species, LocalDate date) {
        return jdbc.sql("SELECT area_name, reason FROM reco.v_svc_excluded WHERE rec_date = ? AND species = ? ORDER BY area_name")
                .params(date, species).query((rs, i) -> new Excluded(rs.getString(1), rs.getString(2))).list();
    }

    public Optional<ModelInfo> model(String version) {
        return jdbc.sql("""
                SELECT version, kind, status, p_at_3, rule_p_at_3, eval_from, eval_until, decision
                FROM reco.v_svc_models WHERE version = ?""")
                .param(version)
                .query((rs, i) -> new ModelInfo(rs.getString(1), rs.getString(2), rs.getString(3), rs.getBigDecimal(4),
                        rs.getBigDecimal(5), rs.getObject(6, LocalDate.class), rs.getObject(7, LocalDate.class), rs.getString(8)))
                .optional();
    }

    /** 최근 weeks 주 (확정된 날) — 그날 서비스한 모델 · 규칙 · 무작위 기대값(좋은 권역 수 ÷ 라벨 있는 권역 수) 평균 */
    public Recent recent(String species, LocalDate today, int weeks) {
        return jdbc.sql("""
                SELECT COUNT(DISTINCT s.rec_date),
                       AVG(s.p_at_3),
                       AVG(r.p_at_3),
                       AVG(JSON_LENGTH(s.good_areas) / s.n_labeled)
                FROM reco.v_svc_live_eval s
                JOIN reco.v_svc_live_eval r ON r.rec_date = s.rec_date AND r.species = s.species AND r.kind = 'rule'
                WHERE s.species = ? AND s.served = 1 AND s.rec_date >= ? AND s.rec_date < ?""")
                .params(species, today.minusWeeks(weeks), today)
                .query((rs, i) -> new Recent(weeks, rs.getInt(1), scale(rs.getBigDecimal(2)), scale(rs.getBigDecimal(3)),
                        scale(rs.getBigDecimal(4))))
                .single();
    }

    public List<HistoryDay> history(String species, LocalDate today, int weeks) {
        return jdbc.sql("""
                SELECT s.rec_date, s.model_version, s.p_at_3, r.p_at_3, JSON_LENGTH(s.good_areas) / s.n_labeled,
                       (SELECT JSON_ARRAYAGG(x.area_name ORDER BY x.rnk) FROM reco.v_svc_rec x
                         WHERE x.rec_date = s.rec_date AND x.species = s.species AND x.rnk <= 3),
                       s.good_areas, s.n_labeled
                FROM reco.v_svc_live_eval s
                JOIN reco.v_svc_live_eval r ON r.rec_date = s.rec_date AND r.species = s.species AND r.kind = 'rule'
                WHERE s.species = ? AND s.served = 1 AND s.rec_date >= ? AND s.rec_date < ?
                ORDER BY s.rec_date DESC""")
                .params(species, today.minusWeeks(weeks), today)
                .query((rs, i) -> new HistoryDay(rs.getObject(1, LocalDate.class), rs.getString(2), rs.getBigDecimal(3),
                        rs.getBigDecimal(4), scale(rs.getBigDecimal(5)), strings(rs.getString(6)), strings(rs.getString(7)),
                        rs.getInt(8)))
                .list();
    }

    public Optional<LocalDate[]> dateRange() {
        return jdbc.sql("SELECT MIN(rec_date), MAX(rec_date) FROM reco.v_svc_rec_run")
                .query((rs, i) -> rs.getObject(1) == null ? null
                        : new LocalDate[] {rs.getObject(1, LocalDate.class), rs.getObject(2, LocalDate.class)})
                .optional();
    }

    private static BigDecimal scale(BigDecimal v) {
        return v == null ? null : v.setScale(3, java.math.RoundingMode.HALF_UP);
    }

    private List<String> strings(String s) {
        return s == null ? List.of() : json.readValue(s, STRINGS);
    }

    private Map<String, Object> map(String s) {
        return s == null ? Map.of() : json.readValue(s, MAP);
    }
}
