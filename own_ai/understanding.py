"""Lightweight multilingual intent and explicit profile-fact extraction."""
from __future__ import annotations
import re
from .language import detect_language,normalize_text

INTENTS={
 "name_recall":["mera naam kya","mera name kya","what is my name","do you remember my name","my name kya"],
 "memory_reason":["kese yaad","kaise yaad","kesay yaad","how do you remember","how do you know my name","why do you know my name"],
 "greeting":["hello","hi","hey","good morning","good evening","good night","salam","assalam","aoa","salaam","السلام","ہیلو","سلام"],
 "identity":["who are you","your name","tum kon","aap kon","ap kon","تم کون","آپ کون","kya tum","what can you do"],
 "thanks":["thank you","thanks","shukriya","bohat shukriya","شکریہ","مہربانی"],
 "goodbye":["bye","goodbye","allah hafiz","khuda hafiz","اللہ حافظ","خدا حافظ"],
 "help":["help me","madad","help chahiye","مدد","رہنمائی"],
}
QUESTION_WORDS={"what","why","how","when","where","who","which","kya","kyun","kaise","kese","kab","kahan","kon","kaun","کیا","کیوں","کیسے","کب","کہاں","کون"}
NAME_STOP={"hai","hy","hain","ha","yaad","rkhna","rakhna","please","plz","remember","mera","meri","name","naam","is","my","kya","kia","what","how","kaise","kese","kon","kaun"}

def _contains_phrase(text: str,phrases: list[str])->bool:
    low=text.casefold()
    return any(re.search(r"(?<!\\w)"+re.escape(p.casefold())+r"(?!\\w)",low) for p in phrases)

def extract_name(text: str)->str|None:
    """Extract only explicit self-identification; never guess from a handle."""
    value=normalize_text(text)
    patterns=[
      r"\\b(?:mera|meri)\\s+(?:naam|name)\\s+(?:hai\\s+)?([A-Za-z][A-Za-z'-]*(?:\\s+[A-Za-z][A-Za-z'-]*){0,2})",
      r"\\bmy\\s+name\\s+is\\s+([A-Za-z][A-Za-z'-]*(?:\\s+[A-Za-z][A-Za-z'-]*){0,2})",
      r"\\bcall\\s+me\\s+([A-Za-z][A-Za-z'-]*(?:\\s+[A-Za-z][A-Za-z'-]*){0,2})",
    ]
    for pattern in patterns:
        match=re.search(pattern,value,flags=re.IGNORECASE)
        if not match:continue
        parts=[]
        for word in match.group(1).split():
            if word.casefold() in NAME_STOP:break
            parts.append(word)
        name=" ".join(parts).strip(" .,!?:;-")
        if name and len(name)<=80:return name[:1].upper()+name[1:]
    return None

def understand(text: str,history: list[dict]|None=None)->dict:
    clean=normalize_text(text); lang=detect_language(clean); intent="conversation"
    for name,phrases in INTENTS.items():
        if _contains_phrase(clean,phrases):intent=name;break
    address_only=bool(re.fullmatch(r"(?i)alexa(?:\\s+(?:baby|dear|hello|hi))?[.! ]*",clean))
    if address_only:intent="greeting"
    tokens=re.findall(r"[\\w\\u0600-\\u06FF']+",clean.casefold())
    is_question=clean.endswith(("?","؟")) or bool(set(tokens)&QUESTION_WORDS)
    if intent=="conversation" and is_question:intent="question"
    return {"text":clean,"language":lang,"intent":intent,"is_question":is_question,
            "has_context":bool(history),"message_length":len(clean),"needs_clarification":len(clean)<2,
            "extracted_name":extract_name(clean),"address_only":address_only}
