"""Heuristic understanding layer; an LLM provider adds semantic depth."""
from __future__ import annotations
import re
from .language import detect_language, normalize_text
INTENTS = {
 "greeting": ["hello","hi","hey","good morning","good evening","good night","salam","assalam","aoa","salaam","السلام","ہیلو","سلام"],
 "identity": ["who are you","your name","tum kon","aap kon","ap kon","تم کون","آپ کون","کya tum","what can you do"],
 "thanks": ["thank you","thanks","shukriya","bohat shukriya","شکریہ","مہربانی"],
 "goodbye": ["bye","goodbye","Allah hafiz","khuda hafiz","اللہ حافظ","خدا حافظ"],
 "help": ["help me","madad","help chahiye","مدد","راهنمائی"],
}
QUESTION_WORDS = {"what","why","how","when","where","who","which","kya","kyun","kaise","kab","kahan","kon","کیا","کیوں","کیسے","کب","کہاں","کون"}
def _contains_phrase(text: str, phrases: list[str]) -> bool:
    low = text.casefold()
    return any(p.casefold() in low for p in phrases)
def understand(text: str, history: list[dict] | None = None) -> dict:
    clean = normalize_text(text)
    lang = detect_language(clean)
    intent = "conversation"
    for name, phrases in INTENTS.items():
        if _contains_phrase(clean, phrases):
            intent = name
            break
    tokens = re.findall(r"[\w\u0600-\u06FF']+", clean.casefold())
    is_question = clean.endswith(("?","؟")) or bool(set(tokens) & QUESTION_WORDS)
    if intent == "conversation" and is_question: intent = "question"
    return {"text":clean,"language":lang,"intent":intent,"is_question":is_question,
            "has_context":bool(history),"message_length":len(clean),
            "needs_clarification":len(clean) < 2}
