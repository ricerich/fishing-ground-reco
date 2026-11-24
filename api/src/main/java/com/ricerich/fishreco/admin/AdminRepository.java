package com.ricerich.fishreco.admin;

import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.ObjectMapper;

/**
 * 관리자 화면이 읽는 reco.v_svc_* 뷰 + app.admin_audit 기록.
 * 뷰의 열을 그대로(snake → camel) 지도로 돌려준다 — 관리자 화면은 열이 자주 늘어나서 DTO 를 따로 두지 않았다.
 * JSON 열(gates · per_species · detail · params)은 문자열이 아니라 구조로 풀어 준다.
 */
@Repository
public class AdminRepository {
    private static final Set<String> JSON_COLS = Set.of("gates", "per_species", "detail", "params");
    private final JdbcClient jdbc;
    private final ObjectMapper json;

    public AdminRepository(JdbcClient jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    private RowMapper<Map<String, Object>> rows() {
        return (ResultSet rs, int i) -> {
            ResultSetMetaData md = rs.getMetaData();
            Map<String, Object> m = new LinkedHashMap<>();
            for (int c = 1; c <= md.getColumnCount(); c++) {
                String col = md.getColumnLabel(c);
                Object v = rs.getObject(c);
                if (v instanceof String s && JSON_COLS.contains(col)) v = parse(s);
                if (v instanceof java.sql.Timestamp t) v = t.toLocalDateTime();
                if (v instanceof java.sql.Date d) v = d.toLocalDate();
                m.put(camel(col), v);
            }
            return m;
        };
    }

    private Object parse(String s) {
        try {
            return json.readValue(s, Object.class);
        } catch (RuntimeException e) {
            return s;
        }
    }

    static String camel(String s) {
        StringBuilder b = new StringBuilder();
        boolean up = false;
        for (char ch : s.toCharArray()) {
            if (ch == '_') up = true;
            else {
                b.append(up ? Character.toUpperCase(ch) : ch);
                up = false;
            }
        }
        return b.toString();
    }

    public Optional<Map<String, Object>> champion() {
        return jdbc.sql("SELECT * FROM reco.v_svc_models WHERE status = 'champion' LIMIT 1").query(rows()).optional();
    }

    public List<Map<String, Object>> models(int limit) {
        return jdbc.sql("SELECT * FROM reco.v_svc_models ORDER BY (status = 'champion') DESC, created_at DESC LIMIT ?")
                .param(limit).query(rows()).list();
    }

    public Optional<Map<String, Object>> model(String version) {
        return jdbc.sql("SELECT * FROM reco.v_svc_models WHERE version = ?").param(version).query(rows()).optional();
    }

    public List<Map<String, Object>> promotions(int limit) {
        return jdbc.sql("SELECT * FROM reco.v_svc_promotions ORDER BY log_id DESC LIMIT ?").param(limit).query(rows()).list();
    }

    public List<Map<String, Object>> jobs(int limit, String job) {
        String where = job == null ? "" : " WHERE job = :job";
        var q = jdbc.sql("SELECT run_id, job, trigger_by, started_at, ended_at, status, summary FROM reco.v_svc_jobs"
                + where + " ORDER BY run_id DESC LIMIT :limit").param("limit", limit);
        if (job != null) q = q.param("job", job);
        return q.query(rows()).list();
    }

    public Optional<Map<String, Object>> job(long runId) {
        return jdbc.sql("SELECT * FROM reco.v_svc_jobs WHERE run_id = ?").param(runId).query(rows()).optional();
    }

    public List<Map<String, Object>> collectSources() {
        return jdbc.sql("SELECT * FROM reco.v_svc_collect ORDER BY FIELD(source, 'auction', 'khoa', 'sea_forecast', 'fishing_index')")
                .query(rows()).list();
    }

    public List<Map<String, Object>> collectLog(int limit, boolean failOnly) {
        return jdbc.sql("SELECT * FROM reco.v_svc_collect_log" + (failOnly ? " WHERE status = '실패'" : "")
                + " ORDER BY log_id DESC LIMIT ?").param(limit).query(rows()).list();
    }

    public Optional<Map<String, Object>> queue(long id) {
        return jdbc.sql("""
                SELECT q.queue_id, q.job, q.params, q.requested_by, q.requested_at, q.status, q.run_id, j.summary, j.status AS run_status
                FROM reco.v_svc_queue q LEFT JOIN reco.v_svc_jobs j ON j.run_id = q.run_id WHERE q.queue_id = ?""")
                .param(id).query(rows()).optional();
    }

    public List<Map<String, Object>> pendingQueue() {
        return jdbc.sql("SELECT * FROM reco.v_svc_queue WHERE status IN ('queued', 'running') ORDER BY queue_id")
                .query(rows()).list();
    }

    public void audit(long userId, String action, String target, String detail) {
        jdbc.sql("INSERT INTO admin_audit (user_id, action, target, detail, created_at) VALUES (?, ?, ?, ?, ?)")
                .params(userId, action, target, detail == null ? null : detail.substring(0, Math.min(500, detail.length())),
                        LocalDateTime.now(com.ricerich.fishreco.config.Today.SEOUL))
                .update();
    }

    /** 물어보기 · 근거 설명 품질 — 최근 N일, LLM 별 */
    public List<Map<String, Object>> ragStats(int days) {
        return jdbc.sql("""
                SELECT llm, mode, COUNT(*) AS n, AVG(cite_ok) AS cite_ok_rate, AVG(numbers_ok) AS numbers_ok_rate,
                       AVG(said_unknown) AS unknown_rate, SUM(helpful = 1) AS helpful_yes, SUM(helpful = 0) AS helpful_no,
                       AVG(seconds) AS avg_seconds
                FROM rag_qa_log WHERE created_at >= NOW() - INTERVAL ? DAY GROUP BY llm, mode ORDER BY n DESC""")
                .param(days).query(rows()).list();
    }

    public List<Map<String, Object>> ragLog(int limit, boolean problemsOnly) {
        return jdbc.sql("""
                SELECT q.qa_id, q.created_at, q.mode, q.species, q.rec_date, q.question, q.answer, q.cite_ok, q.numbers_ok,
                       q.said_unknown, q.made_up, q.llm, q.seconds, q.helpful, u.display_name AS who
                FROM rag_qa_log q LEFT JOIN users u ON u.user_id = q.user_id"""
                + (problemsOnly ? " WHERE q.helpful = 0 OR q.numbers_ok = 0 OR q.made_up > 0" : "")
                + " ORDER BY q.qa_id DESC LIMIT ?").param(limit).query(rows()).list();
    }

    /** 추천 피드백 — 모델(서비스하던 버전)별 · 품목별 */
    public List<Map<String, Object>> feedbackStats(int days) {
        return jdbc.sql("""
                SELECT model_version, species, COUNT(*) AS n, SUM(helpful) AS helpful_yes, SUM(NOT helpful) AS helpful_no
                FROM rec_feedback WHERE created_at >= NOW() - INTERVAL ? DAY
                GROUP BY model_version, species ORDER BY model_version, species""")
                .param(days).query(rows()).list();
    }

    public List<Map<String, Object>> feedbackComments(int limit) {
        return jdbc.sql("""
                SELECT f.rec_date, f.species, f.area_name, f.model_version, f.helpful, f.comment, f.created_at, u.display_name AS who
                FROM rec_feedback f LEFT JOIN users u ON u.user_id = f.user_id
                WHERE f.comment IS NOT NULL ORDER BY f.feedback_id DESC LIMIT ?""")
                .param(limit).query(rows()).list();
    }

    public List<Map<String, Object>> audits(int limit) {
        return jdbc.sql("""
                SELECT a.audit_id, a.action, a.target, a.detail, a.created_at, u.display_name AS who
                FROM admin_audit a LEFT JOIN users u ON u.user_id = a.user_id ORDER BY a.audit_id DESC LIMIT ?""")
                .param(limit).query(rows()).list();
    }
}
