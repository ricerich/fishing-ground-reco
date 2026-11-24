package com.ricerich.fishreco.feedback;

import com.ricerich.fishreco.auth.LoginSessions;
import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.Today;
import com.ricerich.fishreco.reco.RecoController;
import com.ricerich.fishreco.reco.RecoRepository;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.*;

/**
 * 추천 피드백 — 회원이 Top-3 카드마다 '도움이 됐어요 / 아니에요' (한 사람 · 하루 · 품목 · 권역에 한 줄, 다시 누르면 바뀜).
 * 그때 서비스하던 모델 버전을 함께 남겨, 관리자 화면에서 모델별로 모아 본다.
 */
@RestController
@RequestMapping("/api/feedback")
public class FeedbackController {
    public record FeedbackReq(@NotNull LocalDate date, @NotBlank String species, @NotBlank @Size(max = 20) String area,
                              @NotNull Boolean helpful, @Size(max = 300) String comment) {}

    private final JdbcClient jdbc;
    private final RecoRepository reco;
    private final Today today;

    public FeedbackController(JdbcClient jdbc, RecoRepository reco, Today today) {
        this.jdbc = jdbc;
        this.reco = reco;
        this.today = today;
    }

    @GetMapping
    public List<Map<String, Object>> mine(@RequestParam LocalDate date, @RequestParam String species) {
        var p = LoginSessions.current();
        return jdbc.sql("SELECT area_name AS area, helpful, comment FROM rec_feedback WHERE user_id=? AND rec_date=? AND species=?")
                .params(p.userId(), date, species).query().listOfRows();
    }

    @PutMapping
    public Map<String, Object> save(@Valid @RequestBody FeedbackReq r) {
        var p = LoginSessions.current();
        if (!RecoController.SPECIES.contains(r.species())) throw ApiException.badRequest("species", "품목은 " + RecoController.SPECIES + " 중 하나");
        if (r.date().isAfter(today.get().plusDays(1))) throw ApiException.badRequest("date", "아직 오지 않은 날입니다");
        var run = reco.run(r.species(), r.date()).orElseThrow(() -> ApiException.notFound("rec", "그날 추천이 없습니다"));
        String comment = r.comment() == null || r.comment().isBlank() ? null : r.comment().strip();
        jdbc.sql("""
                INSERT INTO rec_feedback (user_id, rec_date, species, area_name, model_version, helpful, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE helpful = VALUES(helpful), comment = COALESCE(VALUES(comment), comment),
                                        model_version = VALUES(model_version), created_at = VALUES(created_at)""")
                .params(p.userId(), r.date(), r.species(), r.area(), run.servedVersion(), r.helpful(), comment, LocalDateTime.now(Today.SEOUL))
                .update();
        return Map.of("area", r.area(), "helpful", r.helpful());
    }
}
