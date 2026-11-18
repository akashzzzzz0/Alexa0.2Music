"""Reply composition and safe fallback responses."""
from __future__ import annotations
from .personality import apply_personality

def compose_reply(answer: str, language: str = "auto") -> str:
    if not answer or not answer.strip():
        answer = {
            "ur": "Maaf kijiye, main is waqt jawab tayyar nahi kar saki. Dobara koshish karein.",
            "roman_urdu": "Sorry, main abhi jawab tayyar nahi kar saki. Dobara try karein.",
        }.get(language, "I couldn't prepare a response just now. Please try again.")
    return apply_personality(answer, language)
