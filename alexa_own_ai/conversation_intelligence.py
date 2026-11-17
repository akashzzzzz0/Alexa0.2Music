"""Bounded turn-level context cues for better multi-turn reference resolution."""
import re

MAX_TURNS = 8
MAX_TURN_CHARS = 180


def _last(history, role):
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == role:
            value = item.get("content")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def build_context_summary(message, history):
    """Build a small transient summary; never persists or invents conversation facts."""
    turns = []
    for item in (history or [])[-MAX_TURNS:]:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            turns.append("{}: {}".format(item["role"], " ".join(content.split())[:MAX_TURN_CHARS]))
    previous_assistant = _last(history, "assistant")
    current = str(message or "").strip()
    reference = bool(re.search(
        r"\b(it|that|this|same|ye|woh|wohi|wahi|us|iska|uska|unhon|phir|kyun|kaise|matlab|mtlb)\b",
        current.casefold(),
    ))
    correction = bool(re.search(
        r"\b(no|nahi|nahin|nhi|galat|wrong|mera matlab|i meant|you misunderstood)\b",
        current.casefold(),
    ))
    asked = bool(previous_assistant and re.search(r"[?؟]\s*$", previous_assistant))
    lines = [
        "Multi-turn context check (transient summary, verify against original turns):",
        "recent_turns=" + (" | ".join(turns) if turns else "none supplied"),
        "contains_context_reference=" + ("yes" if reference else "no"),
        "contains_possible_correction=" + ("yes" if correction else "no"),
        "previous_assistant_question=" + ("yes" if asked else "no"),
        "Resolve references from the closest relevant exchange, not merely the last word. "
        "When a short reply answers the assistant's question, continue that thread. "
        "When the user corrects a detail, replace the mistaken interpretation. "
        "Do not invent missing participants, events, motives, or facts.",
    ]
    return "\n".join(lines)
