"""LLM 백엔드 — 모두 stream(messages) → 글 조각을 차례로 내보내는 같은 모양 (화면이 글자가 써지듯 보이게)

  ollama : 내 PC 의 Ollama (기본). 먼저 `ollama pull qwen3:1.7b`  — 한국어가 더 자연스러운 것: exaone3.5:2.4b
  openai : OPENAI_API_KEY + pip install openai
  claude : ANTHROPIC_API_KEY + pip install anthropic
  mock   : LLM 없이 — answer.py 가 근거 문장을 골라 만든 글을 그대로 흘려보낸다 (생성하지 않음, 화면에 그렇게 표시)

LLM 을 부를 수 없으면 LLMUnavailable 을 던진다 → answer.py 가 mock 으로 바꾸고 화면에 알린다.
"""
import json
import os

import requests

BACKEND = os.getenv("LLM_BACKEND", "ollama").strip() or "ollama"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
TEMPERATURE = 0.2
MAX_TOKENS = 500


class LLMUnavailable(RuntimeError):
    pass


def name(backend=None) -> str:
    b = backend or BACKEND
    return {"ollama": f"ollama:{OLLAMA_MODEL}", "openai": f"openai:{OPENAI_MODEL}", "claude": f"claude:{CLAUDE_MODEL}"}.get(b, "mock")


def status() -> dict:
    """health 용 — 지금 LLM 을 부를 수 있나 (ollama 는 모델을 받아 두었는지까지)"""
    if BACKEND == "ollama":
        try:
            tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json().get("models", [])
            have = [m["name"] for m in tags]
            ok = any(n.split(":")[0] == OLLAMA_MODEL.split(":")[0] for n in have)
            return {"backend": "ollama", "model": OLLAMA_MODEL, "ready": ok,
                    "reason": None if ok else f"모델 없음 — ollama pull {OLLAMA_MODEL}"}
        except requests.RequestException:
            return {"backend": "ollama", "model": OLLAMA_MODEL, "ready": False, "reason": f"Ollama 에 연결할 수 없음 ({OLLAMA_URL})"}
    if BACKEND == "openai":
        return {"backend": "openai", "model": OPENAI_MODEL, "ready": bool(os.getenv("OPENAI_API_KEY")), "reason": None}
    if BACKEND == "claude":
        return {"backend": "claude", "model": CLAUDE_MODEL, "ready": bool(os.getenv("ANTHROPIC_API_KEY")), "reason": None}
    return {"backend": "mock", "model": None, "ready": True, "reason": "LLM 없이 근거 문장만 (LLM_BACKEND=mock)"}


def stream(messages, backend=None):
    b = backend or BACKEND
    if b == "ollama":
        yield from _ollama(messages)
    elif b == "openai":
        yield from _openai(messages)
    elif b == "claude":
        yield from _claude(messages)
    else:
        raise LLMUnavailable("mock")


def _ollama(messages):
    body = {"model": OLLAMA_MODEL, "messages": messages, "stream": True, "think": False,
            "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS}}
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, stream=True, timeout=(3, 300))
        if r.status_code == 400 and "think" in r.text:            # 생각 모드가 없는 모델 → 옵션 빼고 다시
            body.pop("think")
            r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, stream=True, timeout=(3, 300))
        if r.status_code == 404:
            raise LLMUnavailable(f"Ollama 에 {OLLAMA_MODEL} 모델이 없습니다 — ollama pull {OLLAMA_MODEL}")
        r.raise_for_status()
    except requests.RequestException as e:
        raise LLMUnavailable(f"Ollama 에 연결할 수 없습니다 ({OLLAMA_URL}): {type(e).__name__}") from e
    with r:
        for line in r.iter_lines():
            if line:
                d = json.loads(line)
                t = d.get("message", {}).get("content", "")
                if t:
                    yield t
                if d.get("done"):
                    break


def _openai(messages):
    if not os.getenv("OPENAI_API_KEY"):
        raise LLMUnavailable("OPENAI_API_KEY 가 없습니다")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMUnavailable("pip install openai 가 필요합니다") from e
    sys_msg = "\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    try:
        with OpenAI().responses.stream(model=OPENAI_MODEL, instructions=sys_msg, input=rest, max_output_tokens=MAX_TOKENS) as s:
            for ev in s:
                if ev.type == "response.output_text.delta":
                    yield ev.delta
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"OpenAI 오류: {type(e).__name__}") from e


def _claude(messages):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise LLMUnavailable("ANTHROPIC_API_KEY 가 없습니다")
    try:
        import anthropic
    except ImportError as e:
        raise LLMUnavailable("pip install anthropic 가 필요합니다") from e
    sys_msg = "\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    try:
        with anthropic.Anthropic().messages.stream(model=CLAUDE_MODEL, system=sys_msg, messages=rest,
                                                   max_tokens=MAX_TOKENS, temperature=TEMPERATURE) as s:
            yield from s.text_stream
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"Claude 오류: {type(e).__name__}") from e
