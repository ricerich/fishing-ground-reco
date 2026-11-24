package com.ricerich.fishreco.admin;

import com.ricerich.fishreco.ai.AiClient;
import com.ricerich.fishreco.auth.LoginSessions;
import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.Today;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/**
 * 관리자 API — /api/admin/** 은 SecurityConfig 에서 ADMIN 만 통과.
 * 읽기는 reco.v_svc_* 뷰를 직접, 실행(작업 · 되돌리기)은 AI 서버의 job_queue 로 넘긴다 → 작업 프로세스가 실행.
 * 실행 요청은 모두 app.admin_audit 에 남는다 (누가 · 언제 · 무엇을).
 */
@RestController
@RequestMapping("/api/admin")
public class AdminController {
    /** 화면에서 누를 수 있는 작업과 설명 — 이름은 AI 서버 jobs.py 와 같다 */
    static final Map<String, String> JOBS = new LinkedHashMap<>();
    static {
        JOBS.put("collect_daily", "수집 — 위판 · 관측 · 예보 · 낚시지수를 받아 DB 에 넣는다");
        JOBS.put("precompute_today", "오늘 추천 다시 계산");
        JOBS.put("evaluate_live", "지난 추천 채점");
        JOBS.put("retrain_weekly", "재학습 → 교체 조건 5개 → 교체 또는 거절");
        JOBS.put("rag_reindex", "RAG 문서를 다시 읽어 색인 다시 만들기 (ai/rag_docs 를 고친 뒤)");
    }
    static final Map<String, String> DEMO_JOBS = Map.of("demo_weak_champion", "시연 시나리오 — 약한 챔피언으로 바꿔 두기");
    private static final Set<String> FOLLOW = Set.of("queued", "running");

    private final AdminRepository repo;
    private final AiClient ai;
    private final Today today;

    public AdminController(AdminRepository repo, AiClient ai, Today today) {
        this.repo = repo;
        this.ai = ai;
        this.today = today;
    }

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        var p = LoginSessions.current();
        return Map.of("admin", p.name(), "role", p.role());
    }

    /** 첫 화면 한 장 — 챔피언 · 수집 · 최근 작업 · 대기 중인 요청 · 실행할 수 있는 작업 */
    @GetMapping("/overview")
    public Map<String, Object> overview() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("today", today.get());
        out.put("demo", today.demo());
        out.put("champion", repo.champion().orElse(null));
        out.put("collect", repo.collectSources());
        out.put("jobs", repo.jobs(8, null));
        out.put("lastRetrain", repo.jobs(1, "retrain_weekly").stream().findFirst().orElse(null));
        out.put("pending", repo.pendingQueue());
        out.put("promotions", repo.promotions(5));
        Map<String, String> runnable = new LinkedHashMap<>(JOBS);
        if (today.demo()) runnable.putAll(DEMO_JOBS);
        out.put("runnable", runnable);
        out.put("schedule", List.of(
                Map.of("time", "매일 05:00 · 18:30", "job", "collect_daily"),
                Map.of("time", "매일 05:40", "job", "precompute_today"),
                Map.of("time", "매일 06:00", "job", "evaluate_live"),
                Map.of("time", "월요일 03:00", "job", "retrain_weekly")));
        return out;
    }

    @GetMapping("/collect")
    public Map<String, Object> collect(@RequestParam(defaultValue = "80") int limit, @RequestParam(defaultValue = "false") boolean failOnly) {
        return Map.of("sources", repo.collectSources(), "log", repo.collectLog(Math.min(limit, 500), failOnly),
                "lastRun", repo.jobs(1, "collect_daily").stream().findFirst().orElse(Map.of()));
    }

    @GetMapping("/models")
    public List<Map<String, Object>> models(@RequestParam(defaultValue = "40") int limit) {
        return repo.models(Math.min(limit, 200));
    }

    @GetMapping("/models/{version}")
    public Map<String, Object> model(@PathVariable String version) {
        return repo.model(version).orElseThrow(() -> ApiException.notFound("model", "없는 버전: " + version));
    }

    @GetMapping("/promotions")
    public List<Map<String, Object>> promotions(@RequestParam(defaultValue = "50") int limit) {
        return repo.promotions(Math.min(limit, 500));
    }

    @GetMapping("/jobs")
    public List<Map<String, Object>> jobs(@RequestParam(defaultValue = "30") int limit, @RequestParam(required = false) String job) {
        return repo.jobs(Math.min(limit, 200), job);
    }

    @GetMapping("/jobs/{runId}")
    public Map<String, Object> job(@PathVariable long runId) {
        return repo.job(runId).orElseThrow(() -> ApiException.notFound("job", "없는 작업 기록: " + runId));
    }

    /** 작업 실행 요청 → 202 + 요청 번호. 화면은 /queue/{id} 를 몇 초마다 읽어 끝났는지 본다 */
    @PostMapping("/jobs/{name}")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Map<String, Object> run(@PathVariable String name, @RequestBody(required = false) Map<String, Object> params) {
        boolean ok = JOBS.containsKey(name) || (today.demo() && DEMO_JOBS.containsKey(name));
        if (!ok) throw ApiException.badRequest("job", "실행할 수 없는 작업: " + name);
        return enqueue(name, params == null ? Map.of() : params);
    }

    @PostMapping("/models/{version}/rollback")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Map<String, Object> rollback(@PathVariable String version) {
        var m = repo.model(version).orElseThrow(() -> ApiException.notFound("model", "없는 버전: " + version));
        if ("champion".equals(m.get("status"))) throw ApiException.conflict("already", version + " 은 이미 챔피언입니다");
        if ("rejected".equals(m.get("status")) && !"rule".equals(m.get("kind"))) {
            throw ApiException.unprocessable("rejected", "교체 조건을 통과하지 못한 후보는 되돌리기 대상이 아닙니다. 예전 챔피언이나 규칙을 고르세요.");
        }
        return enqueue("rollback", Map.of("version", version));
    }

    private Map<String, Object> enqueue(String name, Map<String, Object> params) {
        var p = LoginSessions.current();
        String who = p.email() != null ? p.email() : p.name();
        Map<String, Object> r = ai.post("/internal/jobs/" + name, Map.of("requested_by", who, "params", params));
        repo.audit(p.userId(), "job:" + name, String.valueOf(r.get("queue_id")), params.isEmpty() ? null : params.toString());
        return r;
    }

    @GetMapping("/queue/{id}")
    public Map<String, Object> queue(@PathVariable long id) {
        var q = repo.queue(id).orElseThrow(() -> ApiException.notFound("queue", "없는 요청: " + id));
        q.put("done", !FOLLOW.contains(String.valueOf(q.get("status"))));
        return q;
    }

    /** 이용 기록 — 물어보기 · 근거 설명의 답 품질과 추천 피드백 */
    @GetMapping("/usage")
    public Map<String, Object> usage(@RequestParam(defaultValue = "30") int days, @RequestParam(defaultValue = "false") boolean problemsOnly) {
        int d = Math.max(1, Math.min(days, 365));
        return Map.of("days", d, "ragStats", repo.ragStats(d), "ragLog", repo.ragLog(15, problemsOnly),
                "feedbackStats", repo.feedbackStats(d), "comments", repo.feedbackComments(20), "audit", repo.audits(20));
    }

    @GetMapping("/audit")
    public List<Map<String, Object>> audit(@RequestParam(defaultValue = "30") int limit) {
        return repo.audits(Math.min(limit, 200));
    }
}
