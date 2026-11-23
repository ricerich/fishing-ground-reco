package com.ricerich.fishreco.reco;

import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import com.ricerich.fishreco.config.Today;
import com.ricerich.fishreco.reco.RecoDtos.*;
import java.time.LocalDate;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** 추천 조회 — 미리 계산된 표를 읽기만 한다 (AI 서버가 꺼져 있어도 동작) */
@RestController
@RequestMapping("/api")
public class RecoController {
    public static final List<String> SPECIES = List.of("고등어", "방어", "삼치");
    static final List<String> NOTES = List.of(
            "점수는 '평소의 1.5배 이상 위판될' 가능성으로 권역의 순서를 정하는 값입니다. 확률로 읽지 마세요.",
            "권역 = 위판장이 있는 항구 근처 바다입니다. 위판 자료에는 실제로 어디서 잡혔는지가 없습니다.",
            "어제 위판은 며칠에 걸쳐 채워집니다. 아침에는 덜 채워진 값으로 계산됩니다.");
    private final RecoRepository repo;
    private final Today today;
    private final AppProperties props;

    public RecoController(RecoRepository repo, Today today, AppProperties props) {
        this.repo = repo;
        this.today = today;
        this.props = props;
    }

    @GetMapping("/meta")
    public Meta meta() {
        var range = repo.dateRange().orElse(new LocalDate[] {null, null});
        return new Meta(today.get(), today.demo(), SPECIES, range[0], range[1], props.demoLogin());
    }

    @GetMapping("/species")
    public List<String> species() {
        return SPECIES;
    }

    @GetMapping("/areas")
    public List<Area> areas() {
        return repo.areas();
    }

    @GetMapping("/recommendations")
    public Recommendation recommendations(@RequestParam String species,
                                          @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
                                          @RequestParam(defaultValue = "3") int k) {
        checkSpecies(species);
        if (k < 1 || k > 14) throw ApiException.badRequest("k", "k 는 1 ~ 14");
        LocalDate d = date == null ? today.get() : date;
        var run = repo.run(species, d);
        if (run.isEmpty()) {
            String msg = d.isAfter(today.get())
                    ? d + " 추천은 아직 계산되지 않았습니다 — 그 전날 저녁(18:30) 수집 뒤에 계산됩니다."
                    : d + " 의 추천 기록이 없습니다.";
            return new Recommendation(species, d, false, msg, null, null, null, List.of(), List.of(), List.of(), NOTES);
        }
        var items = repo.items(species, d);
        var model = repo.model(run.get().servedVersion()).orElse(null);
        var recent = repo.recent(species, today.get(), 8);
        return new Recommendation(species, d, true, null, run.get(), model, recent,
                items.stream().limit(k).toList(), items.stream().skip(k).toList(), repo.excluded(species, d), NOTES);
    }

    @GetMapping("/recommendations/history")
    public History history(@RequestParam String species, @RequestParam(defaultValue = "8") int weeks) {
        checkSpecies(species);
        if (weeks < 1 || weeks > 26) throw ApiException.badRequest("weeks", "weeks 는 1 ~ 26");
        return new History(species, weeks, repo.recent(species, today.get(), weeks), repo.history(species, today.get(), weeks));
    }

    static void checkSpecies(String species) {
        if (!SPECIES.contains(species)) throw ApiException.badRequest("species", "품목은 " + SPECIES + " 중 하나");
    }
}
