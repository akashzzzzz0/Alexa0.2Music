"""Optional adapter for a self-hosted OpenAI-compatible local language model.

The model is hosted by the operator (for example, on their own device/server).
No third-party AI provider is selected or contacted by this module.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 35
MAX_CONTEXT_MESSAGES = 20
MAX_MESSAGE_CHARS = 6000


def _endpoint(base_url):
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        return ""
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return value + "/chat/completions"
    return value + "/v1/chat/completions"


def generate(message, history):
    """Return a model reply, or None when no local model is configured/unavailable."""
    endpoint = _endpoint(os.getenv("ALEXA_LOCAL_MODEL_URL", ""))
    if not endpoint or not str(message or "").strip():
        return None

    model_name = os.getenv("ALEXA_LOCAL_MODEL_NAME", "local-model")
    token = os.getenv("ALEXA_LOCAL_MODEL_TOKEN", "")
    try:
        timeout = float(os.getenv("ALEXA_LOCAL_MODEL_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    timeout = min(max(timeout, 3), 90)

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
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()
        if content:
            messages.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    messages.append({"role": "user", "content": str(message).strip()[:MAX_MESSAGE_CHARS]})

    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                return None
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
