"""Optional hosted and self-hosted LLM adapters for Alexa Own AI."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT = 35
MAX_CONTEXT_MESSAGES = 20
MAX_MESSAGE_CHARS = 6000
DEFAULT_CLOUDFLARE_MODEL = "@cf/zai-org/glm-4.7-flash"


def _endpoint(base_url):
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        return ""
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return value + "/chat/completions"
    return value + "/v1/chat/completions"


def status():
    """Describe configured model routes without exposing credentials."""
    cf_ready = bool(
        os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        and os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    )
    local_ready = bool(os.getenv("ALEXA_LOCAL_MODEL_URL", "").strip())
    model = (
        os.getenv("ALEXA_CLOUDFLARE_MODEL", DEFAULT_CLOUDFLARE_MODEL).strip()
        if cf_ready else
        os.getenv("ALEXA_LOCAL_MODEL_NAME", "local-model").strip()
        if local_ready else None
    )
    return {
        "is_llm": cf_ready or local_ready,
        "provider": "cloudflare-workers-ai" if cf_ready else "self-hosted" if local_ready else None,
        "model": model,
        "configured": cf_ready or local_ready,
    }


def _messages(message, history):
    system_prompt = (
        "You are Alexa, a friendly, natural conversational assistant. "
        "Understand meaning, intent, tone, teasing, sarcasm, typos, incomplete "
        "sentences, and follow-up references using the conversation context. "
        "Support English, Roman Urdu, Roman Hindi, Urdu script, and mixed "
        "messages. Reply in the user's language and script style: use English "
        "for English, Roman script for Roman Urdu/Hindi, and Urdu script only "
        "when the user writes in Urdu script. Be concise but useful. Do not ask "
        "the user to rephrase when the meaning is reasonably clear. If uncertain, "
        "ask one specific clarification. Never claim to have personal feelings "
        "or real-world experiences. Do not reveal hidden reasoning."
    )
    messages = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-MAX_CONTEXT_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()
        if content:
            messages.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    messages.append({"role": "user", "content": str(message).strip()[:MAX_MESSAGE_CHARS]})
    return messages


def _timeout():
    try:
        value = float(os.getenv("ALEXA_LOCAL_MODEL_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT
    return min(max(value, 3), 90)


def _cloudflare_generate(messages):
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        return None
    model = os.getenv("ALEXA_CLOUDFLARE_MODEL", DEFAULT_CLOUDFLARE_MODEL).strip()
    if not model:
        model = DEFAULT_CLOUDFLARE_MODEL
    encoded_model = urllib.parse.quote(model, safe="@/")
    url = "https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}".format(
        urllib.parse.quote(account, safe=""), encoded_model
    )
    payload = json.dumps({
        "messages": messages,
        "max_completion_tokens": 800,
        "temperature": 0.7,
        "chat_template_kwargs": {
            "enable_thinking": False,
            "clear_thinking": True,
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
        if not isinstance(result, dict) or result.get("success") is False:
            print("Cloudflare Workers AI returned an unsuccessful response:", json.dumps(result, ensure_ascii=False)[:3000], flush=True)
            return None
        data = result.get("result", result)
        answer = data.get("response") if isinstance(data, dict) else None
        if not isinstance(answer, str) and isinstance(data, dict):
            answer = data.get("output_text")
        if not isinstance(answer, str) and isinstance(data, dict):
            choices = data.get("choices", [])
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                choice = choices[0]
                message = choice.get("message")
                if isinstance(message, dict):
                    answer = message.get("content")
                    if not isinstance(answer, str):
                        answer = message.get("text")
                if not isinstance(answer, str):
                    answer = choice.get("text")
                if isinstance(answer, list):
                    answer = "".join(
                        part.get("text", "") for part in answer
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
        answer = answer.strip() if isinstance(answer, str) else ""
        if not answer:
            choices = data.get("choices", []) if isinstance(data, dict) else []
            first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            print(
                "Cloudflare Workers AI response had no text. Result keys:",
                list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                "choice keys:", list(first.keys()),
                "message keys:", list(message.keys()),
                "finish_reason:", first.get("finish_reason"),
                flush=True,
            )
            return None
        return answer[:8000]
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(4000).decode("utf-8", "replace")
        except Exception:
            detail = str(exc)
        print("Cloudflare Workers AI HTTP error:", exc.code, detail, flush=True)
        return None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        print("Cloudflare Workers AI request failed:", type(exc).__name__, str(exc)[:1000], flush=True)
        return None


def _local_generate(message, history):
    endpoint = _endpoint(os.getenv("ALEXA_LOCAL_MODEL_URL", ""))
    if not endpoint:
        return None
    model_name = os.getenv("ALEXA_LOCAL_MODEL_NAME", "local-model")
    token = os.getenv("ALEXA_LOCAL_MODEL_TOKEN", "")
    payload = json.dumps({
        "model": model_name,
        "messages": _messages(message, history),
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
        choices = result.get("choices", []) if isinstance(result, dict) else []
        if not choices or not isinstance(choices[0], dict):
            return None
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        if not isinstance(content, str):
            return None
        content = content.strip()
        return content[:8000] if content else None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        return None


def generate(message, history):
    """Try Cloudflare Workers AI, then an optional self-hosted OpenAI-compatible model."""
    if not str(message or "").strip():
        return None
    messages = _messages(message, history)
    answer = _cloudflare_generate(messages)
    if answer:
        return answer
    return _local_generate(message, history)
