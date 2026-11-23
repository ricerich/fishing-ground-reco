package com.ricerich.fishreco.common;

import org.springframework.http.HttpStatus;

/** 화면에 그대로 보여 줄 한국어 메시지를 담는 예외 — ApiExceptionHandler 가 ProblemDetail 로 바꾼다. */
public class ApiException extends RuntimeException {
    private final HttpStatus status;
    private final String code;

    public ApiException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public HttpStatus status() { return status; }

    public String code() { return code; }

    public static ApiException badRequest(String code, String msg) { return new ApiException(HttpStatus.BAD_REQUEST, code, msg); }

    public static ApiException notFound(String code, String msg) { return new ApiException(HttpStatus.NOT_FOUND, code, msg); }

    public static ApiException conflict(String code, String msg) { return new ApiException(HttpStatus.CONFLICT, code, msg); }

    public static ApiException unprocessable(String code, String msg) { return new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, code, msg); }

    public static ApiException unavailable(String code, String msg) { return new ApiException(HttpStatus.SERVICE_UNAVAILABLE, code, msg); }

    public static ApiException tooMany(String code, String msg) { return new ApiException(HttpStatus.TOO_MANY_REQUESTS, code, msg); }
}
