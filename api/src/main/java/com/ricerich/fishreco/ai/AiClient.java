package com.ricerich.fishreco.ai;

import com.ricerich.fishreco.common.ApiException;
import com.ricerich.fishreco.config.AppProperties;
import java.io.InputStream;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

/** AI 서버(FastAPI) 호출 — 모든 요청에 X-Internal-Token. 브라우저는 AI 서버를 직접 부르지 않는다. */
@Component
public class AiClient {
    private final RestClient http;
    private final boolean tokenSet;

    public AiClient(AppProperties props) {
        var jdk = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
        var factory = new JdkClientHttpRequestFactory(jdk);
        factory.setReadTimeout(Duration.ofSeconds(props.ai().timeoutSeconds()));
        String token = props.ai().internalToken() == null ? "" : props.ai().internalToken();
        this.tokenSet = !token.isBlank();
        this.http = RestClient.builder().baseUrl(props.ai().baseUrl()).requestFactory(factory)
                .defaultHeader("X-Internal-Token", token).build();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> health() {
        return call(() -> http.get().uri("/health").retrieve().body(Map.class));
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> post(String path, Object body) {
        requireToken();
        return call(() -> http.post().uri(path).contentType(MediaType.APPLICATION_JSON).body(body).retrieve().body(Map.class));
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> get(String path) {
        requireToken();
        return call(() -> http.get().uri(path).retrieve().body(Map.class));
    }

    /** NDJSON 스트림을 그대로 받아 넘긴다 (RAG). 호출한 쪽이 스트림을 닫는다. */
    public InputStream stream(String path, Object body) {
        requireToken();
        try {
            return http.post().uri(path).contentType(MediaType.APPLICATION_JSON).body(body)
                    .exchange((req, res) -> {
                        if (res.getStatusCode().isError()) {
                            throw ApiException.unavailable("ai", "AI 서버 응답 " + res.getStatusCode().value());
                        }
                        return res.getBody();
                    }, false);
        } catch (ResourceAccessException e) {
            throw ApiException.unavailable("ai_down", "AI 서버에 연결할 수 없습니다 — 잠시 뒤 다시 시도해 주세요");
        }
    }

    private void requireToken() {
        if (!tokenSet) throw ApiException.unavailable("ai_token", "INTERNAL_TOKEN 이 설정되지 않았습니다");
    }

    private <T> T call(java.util.function.Supplier<T> s) {
        try {
            return s.get();
        } catch (ResourceAccessException e) {
            throw ApiException.unavailable("ai_down", "AI 서버에 연결할 수 없습니다 — 잠시 뒤 다시 시도해 주세요");
        } catch (RestClientResponseException e) {
            throw new ApiException(org.springframework.http.HttpStatus.valueOf(e.getStatusCode().value()), "ai",
                    "AI 서버: " + e.getResponseBodyAsString());
        }
    }
}
