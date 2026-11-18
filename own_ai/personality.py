"""Alexa's consistent, friendly feminine conversational style."""
from __future__ import annotations

def apply_personality(text: str, language: str = "auto") -> str:
    text = (text or "").strip()
    if not text:
        return "Mujhe aapki baat samajhne ke liye thori aur detail chahiye."
    # Keep the user's language and meaning; avoid forced greetings or excessive emojis.
    return text
