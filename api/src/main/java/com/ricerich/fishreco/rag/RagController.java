package com.ricerich.fishreco.rag;

import com.ricerich.fishreco.ai.AiClient;
import com.ricerich.fishreco.auth.AppPrincipal;
import com.ricerich.fishreco.auth.LoginSessions;
import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import com.ricerich.fishreco.config.Today;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

/**
 * RAG 중계 — 화면 ↔ Spring ↔ AI 서버. 회원만, 1분에 N번(app.rag.per-minute).
 * 응답 스트림에 직접 쓰고 줄마다 flush 한다. (비동기 StreamingResponseBody 로 했더니 이 구성에서 끝까지 모았다가
 * 한 번에 보내져 '써지는' 모양이 사라졌다 — 요청 스레드 하나를 답이 끝날 때까지 쓰는 대신 확실히 흘려보낸다)
 * AI 서버의 NDJSON 스트림을 한 줄씩 그대로 흘려보내면서, 마지막 'done' 줄을 읽어 rag_qa_log 에 남기고
 * 'logged' 줄(qaId)을 하나 더 보낸다 → 화면이 '도움이 됐어요' 를 그 번호로 보낸다.
 */
@RestController
@RequestMapping("/api/rag")
public class RagController {
    public record Turn(@NotBlank String role, @NotBlank @Size(max = 1200) String content) {}

    public record AskReq(@NotBlank @Size(min = 2, max = 300) String question, @Size(max = 8) List<Turn> history) {}

    public record ExplainReq(@NotBlank String species, @NotNull LocalDate date, @NotBlank @Size(max = 20) String area) {}

    public record Feedback(@NotNull Boolean helpful) {}

    private final AiClient ai;
    private final JdbcClient jdbc;
    private final ObjectMapper json;
    private final AppProperties props;
    private final Map<Long, Deque<Instant>> recent = new ConcurrentHashMap<>();

    public RagController(AiClient ai, JdbcClient jdbc, ObjectMapper json, AppProperties props) {
        this.ai = ai;
        this.jdbc = jdbc;
        this.json = json;
        this.props = props;
    }

    @PostMapping("/ask")
    public void ask(@Valid @RequestBody AskReq r, jakarta.servlet.http.HttpServletResponse res) throws java.io.IOException {
        AppPrincipal p = LoginSessions.current();
        limit(p.userId());
        Map<String, Object> body = Map.of("question", r.question().strip(), "history", r.history() == null ? List.of() : r.history());
        relay(p.userId(), "ask", r.question().strip(), null, null, ai.stream("/internal/rag/ask", body), res);
    }

    @PostMapping("/explain")
    public void explain(@Valid @RequestBody ExplainReq r, jakarta.servlet.http.HttpServletResponse res) throws java.io.IOException {
        AppPrincipal p = LoginSessions.current();
        limit(p.userId());
        Map<String, Object> body = Map.of("species", r.species(), "date", r.date().toString(), "area", r.area());
        String q = "왜 " + r.area() + " 인가요? (" + r.date() + " " + r.species() + ")";
        relay(p.userId(), "explain", q, r.species(), r.date(), ai.stream("/internal/rag/explain", body), res);
    }

    @PostMapping("/{qaId}/feedback")
    public Map<String, Object> feedback(@PathVariable long qaId, @Valid @RequestBody Feedback f) {
        AppPrincipal p = LoginSessions.current();
        int n = jdbc.sql("UPDATE rag_qa_log SET helpful = ? WHERE qa_id = ? AND user_id = ?").params(f.helpful(), qaId, p.userId()).update();
        if (n == 0) throw ApiException.notFound("qa", "없는 답입니다");
        return Map.of("qaId", qaId, "helpful", f.helpful());
    }

    /** 1분 창 안의 요청 수 — 서버 한 대 기준(메모리). 여러 대면 Redis 등으로 옮긴다 */
    private void limit(long userId) {
        int max = Math.max(1, props.rag().perMinute());
        Instant now = Instant.now();
        Deque<Instant> q = recent.computeIfAbsent(userId, k -> new ArrayDeque<>());
        synchronized (q) {
            while (!q.isEmpty() && q.peekFirst().isBefore(now.minusSeconds(60))) q.pollFirst();
            if (q.size() >= max) {
                long wait = 60 - (now.getEpochSecond() - q.peekFirst().getEpochSecond());
                throw ApiException.tooMany("rag_limit", "질문은 1분에 " + max + "번까지입니다. " + Math.max(1, wait) + "초 뒤 다시 물어 주세요.");
            }
            q.addLast(now);
        }
    }

    private void relay(long userId, String mode, String question, String species, LocalDate date, InputStream in,
                       jakarta.servlet.http.HttpServletResponse res) throws java.io.IOException {
        res.setContentType("application/x-ndjson;charset=UTF-8");
        res.setHeader("X-Accel-Buffering", "no");
        res.setHeader("Cache-Control", "no-cache");
        OutputStream out = res.getOutputStream();
        {
            JsonNode meta = null, done = null;
            try (in; var reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isBlank()) continue;
                    out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                    out.flush();                                    // 한 줄씩 바로 — 화면에 글자가 써지듯
                    if (line.startsWith("{\"type\": \"meta\"") || line.startsWith("{\"type\":\"meta\"")) meta = json.readTree(line);
                    else if (line.contains("\"type\": \"done\"") || line.contains("\"type\":\"done\"")) done = json.readTree(line);
                }
            }
            if (done != null) {
                long id = log(userId, mode, question, species, date, meta, done);
                out.write(("{\"type\":\"logged\",\"qaId\":" + id + "}\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        }
    }

    private long log(long userId, String mode, String question, String species, LocalDate date, JsonNode meta, JsonNode done) {
        var key = new org.springframework.jdbc.support.GeneratedKeyHolder();
        JsonNode c = done.path("check");
        String sources = meta == null ? "[]" : json.writeValueAsString(meta.path("sources").valueStream().map(s -> s.path("id").asString()).toList());
        jdbc.sql("""
                INSERT INTO rag_qa_log (user_id, mode, species, rec_date, question, answer, sources, cite_ok, said_unknown, made_up,
                                        numbers_ok, llm, seconds, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""")
                .params(userId, mode, species, date, question.length() > 500 ? question.substring(0, 500) : question,
                        done.path("answer").asString(""), sources, c.path("cite_ok").asBoolean(false), c.path("said_unknown").asBoolean(false),
                        c.path("made_up").size(), c.path("numbers_ok").asBoolean(true), done.path("llm").asString(""),
                        done.path("seconds").asDouble(0), LocalDateTime.now(Today.SEOUL))
                .update(key, "qa_id");                    // 같은 연결에서 받은 번호 (LAST_INSERT_ID 를 따로 물으면 다른 연결일 수 있다)
        return key.getKey().longValue();
    }
}
