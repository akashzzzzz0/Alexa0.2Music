"""Lightweight language identification and normalization for Urdu/Roman Urdu/English."""
from __future__ import annotations
import re

URDU = re.compile(r"[\u0600-\u06FF]")
ROMAN_URDU_HINTS = {"hai","hain","ho","kya","kyun","kaise","kr","karo","karna","mujhe","tum","aap","acha","nahi","haan","batao","wala","wali","mein","mera","meri","apni","samjho"}

def detect_language(text: str) -> str:
    text = text or ""
    if URDU.search(text):
        return "ur"
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if len(words & ROMAN_URDU_HINTS) >= 1:
        return "roman_urdu"
    return "en"

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
