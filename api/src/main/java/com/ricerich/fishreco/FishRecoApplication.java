package com.ricerich.fishreco;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

/** 어장 추천 서비스 백엔드 — 회원 · 추천 조회 · RAG 중계 · 관리자 API. AI 서버(FastAPI)는 안쪽에서만 부른다. */
@SpringBootApplication
@ConfigurationPropertiesScan
@EnableJpaRepositories(considerNestedRepositories = true)   // user/Repositories 안에 모아 둔 인터페이스까지 찾게
public class FishRecoApplication {
    public static void main(String[] args) {
        SpringApplication.run(FishRecoApplication.class, args);
    }
}
