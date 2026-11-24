package com.ricerich.fishreco.admin;

import com.ricerich.fishreco.auth.LoginSessions;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 관리자 API — /api/admin/** 은 SecurityConfig 에서 ADMIN 만 통과. 수집 · 모델 · 작업은 3단계에서 더한다 */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        var p = LoginSessions.current();
        return Map.of("admin", p.name(), "role", p.role());
    }
}
