package com.ricerich.fishreco.common;

import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/** 모든 오류를 RFC 9457 ProblemDetail 로 — {status, title, detail, code, fields} */
@RestControllerAdvice
public class ApiExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    ProblemDetail api(ApiException e) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(e.status(), e.getMessage());
        p.setProperty("code", e.code());
        return p;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ProblemDetail invalid(MethodArgumentNotValidException e) {
        Map<String, String> fields = new LinkedHashMap<>();
        e.getBindingResult().getFieldErrors().forEach(f -> fields.putIfAbsent(f.getField(), f.getDefaultMessage()));
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "입력값을 확인해 주세요");
        p.setProperty("code", "invalid");
        p.setProperty("fields", fields);
        return p;
    }

    @ExceptionHandler({MissingServletRequestParameterException.class, MethodArgumentTypeMismatchException.class})
    ProblemDetail badParam(Exception e) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "요청 값이 올바르지 않습니다: " + e.getMessage());
        p.setProperty("code", "bad_param");
        return p;
    }

    @ExceptionHandler(org.springframework.dao.DataAccessException.class)
    ProblemDetail db(Exception e) {
        log.error("DB 오류", e);
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.SERVICE_UNAVAILABLE, "데이터베이스에 연결할 수 없습니다");
        p.setProperty("code", "db");
        return p;
    }
}
