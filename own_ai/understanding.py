"""Intent and conversational-context understanding."""
from __future__ import annotations
from .language import detect_language, normalize_text

def understand(text: str, history: list[dict] | None = None) -> dict:
    clean = normalize_text(text)
    lower = clean.lower()
    intent = "conversation"
    if any(x in lower for x in ("hello","hi","salam","assalam","hey","aoa")): intent = "greeting"
    elif any(x in lower for x in ("who are you","tum kon","aap kon","your name")): intent = "identity"
    elif any(x in lower for x in ("thank","shukriya","thanks")): intent = "thanks"
    elif clean.endswith("?") or any(x in lower.split() for x in ("kya","kaise","kyun","what","why","how","when","where")): intent = "question"
    return {"text": clean, "language": detect_language(clean), "intent": intent, "has_context": bool(history)}
