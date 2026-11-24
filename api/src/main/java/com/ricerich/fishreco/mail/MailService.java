package com.ricerich.fishreco.mail;

import com.ricerich.fishreco.config.AppProperties;
import jakarta.mail.internet.MimeMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

/** 인증 · 재설정 메일. 개발 · 수업은 Mailpit(받은 편지함 http://localhost:8025)에서 확인한다. */
@Service
public class MailService {
    private static final Logger log = LoggerFactory.getLogger(MailService.class);
    private final JavaMailSender sender;
    private final AppProperties props;

    public MailService(JavaMailSender sender, AppProperties props) {
        this.sender = sender;
        this.props = props;
    }

    public void verifyEmail(String to, String name, String token) {
        String link = props.webBaseUrl() + "/verify?token=" + token;
        send(to, "[어장 추천] 이메일 주소를 확인해 주세요",
                name + "님, 가입해 주셔서 고맙습니다.",
                "아래 버튼을 누르면 가입이 끝납니다. 이 링크는 24시간 동안, 한 번만 쓸 수 있습니다.",
                "이메일 확인하기", link,
                "직접 가입하지 않았다면 이 메일을 지워 주세요. 아무 일도 일어나지 않습니다.");
    }

    public void resetPassword(String to, String name, String token) {
        String link = props.webBaseUrl() + "/reset?token=" + token;
        send(to, "[어장 추천] 비밀번호 재설정",
                name + "님, 비밀번호 재설정을 요청하셨습니다.",
                "아래 버튼을 눌러 새 비밀번호를 정해 주세요. 이 링크는 30분 동안, 한 번만 쓸 수 있습니다. 재설정하면 다른 기기의 로그인은 모두 끊깁니다.",
                "새 비밀번호 정하기", link,
                "요청하지 않았다면 이 메일을 무시하세요. 비밀번호는 바뀌지 않습니다.");
    }

    private void send(String to, String subject, String hello, String body, String button, String link, String foot) {
        try {
            MimeMessage m = sender.createMimeMessage();
            var h = new MimeMessageHelper(m, true, "UTF-8");
            h.setFrom(props.mail().from());
            h.setTo(to);
            h.setSubject(subject);
            String text = hello + "\n\n" + body + "\n\n" + link + "\n\n" + foot;
            String html = """
                    <div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:520px;color:#0e2a3b">
                      <p style="font-size:18px;font-weight:700">%s</p>
                      <p style="line-height:1.7">%s</p>
                      <p><a href="%s" style="display:inline-block;background:#0e2a3b;color:#eef4f4;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:700">%s</a></p>
                      <p style="font-size:13px;color:#3c5566">버튼이 안 되면 이 주소를 붙여 넣으세요: %s</p>
                      <p style="font-size:13px;color:#3c5566">%s</p>
                    </div>""".formatted(hello, body, link, button, link, foot);
            h.setText(text, html);
            sender.send(m);
        } catch (Exception e) {
            log.error("메일 보내기 실패 ({}): {}", subject, e.getMessage());
            throw com.ricerich.fishreco.common.ApiException.unavailable("mail", "메일을 보내지 못했습니다 — 메일 서버 설정을 확인해 주세요");
        }
    }
}
