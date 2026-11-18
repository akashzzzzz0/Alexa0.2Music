"""Robust lightweight language/script detection for Urdu, Roman Urdu and English."""
from __future__ import annotations
import re
URDU_RE = re.compile(r"[\u0600-\u06FF]")
ROMAN_URDU = set("""hai hain ho hun houn kya kyun kyu kaise kese kahan kab kon kaun kis kisay kise mujhe mjhe apko aap ap tum tumhara mera meri mere tera teri nahi nahin nhi ni haan han acha achha theek thik batao btao kr kar karo kro karna karni chahiye chahta chahti raha rahi gaya gayi wala wali walay mein main mai hum ham unka iska uska yeh ye woh wo idhar udhar abhi phir lekin magar kyunki q k""".split())
def normalize_text(text: str) -> str:
    text = (text or "").replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()
def detect_language(text: str) -> str:
    text = normalize_text(text)
    if not text: return "unknown"
    urdu_chars = len(URDU_RE.findall(text))
    latin_words = re.findall(r"[a-zA-Z']+", text.lower())
    if urdu_chars and (not latin_words or urdu_chars >= len("".join(latin_words)) * 0.35):
        return "ur"
    words = set(w.lower() for w in latin_words)
    roman_hits = len(words & ROMAN_URDU)
    if roman_hits >= 2 or (roman_hits >= 1 and len(words) <= 5):
        return "roman_urdu"
    return "en"
def language_name(code: str) -> str:
    return {"ur":"Urdu","roman_urdu":"Roman Urdu","en":"English","unknown":"the user's language"}.get(code, "the user's language")
