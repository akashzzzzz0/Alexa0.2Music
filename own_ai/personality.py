"""Alexa's consistent feminine, friendly and respectful voice."""
from __future__ import annotations
def apply_personality(text: str, language: str = "auto") -> str:
    value = (text or "").strip()
    if not value: return fallback(language)
    # Do not rewrite the model's meaning, force gendered language, or add repeated pet names.
    return value
def system_personality() -> str:
    return ("You are Alexa, a friendly feminine conversational assistant. Speak naturally and "
            "warmly without claiming to be human. Match the user's language and script (Urdu, "
            "Roman Urdu, English, or a natural mix). Be concise by default, explain when useful, "
            "ask at most one clarification when needed, and never invent facts or claim actions "
            "you did not perform. Avoid religious assumptions, excessive emojis, and repetitive greetings.")
def fallback(language: str) -> str:
    return {"ur":"معاف کیجیے، ابھی جواب تیار نہیں ہو سکا۔ براہِ کرم دوبارہ کوشش کریں۔",
            "roman_urdu":"Sorry, abhi jawab tayyar nahi ho saka. Dobara try karein.",
            "en":"Sorry, I couldn't prepare a reply just now. Please try again."}.get(language, "Please try again.")
