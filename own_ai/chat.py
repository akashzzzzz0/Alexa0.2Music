"""Main Alexa conversational orchestration layer."""
from __future__ import annotations
from .memory import ConversationMemory
from .understanding import understand
from .reasoning import build_plan
from .reply import compose_reply

class AlexaAI:
    def __init__(self, responder=None):
        self.memory = ConversationMemory()
        self.responder = responder
    async def chat(self, message: str, conversation_id: str = "default") -> dict:
        history = self.memory.get(conversation_id)
        parsed = understand(message, history)
        plan = build_plan(message, parsed, history)
        if self.responder:
            result = self.responder(message=message, history=history, understanding=parsed, plan=plan)
            if hasattr(result, "__await__"):
                result = await result
            answer = str(result)
        else:
            answer = self._fallback(parsed)
        answer = compose_reply(answer, parsed["language"])
        self.memory.add(conversation_id, "user", message)
        self.memory.add(conversation_id, "assistant", answer)
        return {"reply": answer, "language": parsed["language"], "intent": parsed["intent"]}
    @staticmethod
    def _fallback(parsed: dict) -> str:
        lang, intent = parsed["language"], parsed["intent"]
        if intent == "greeting":
            return {"ur":"وعلیکم السلام! بتائیں، میں آپ کی کیا مدد کر سکتی ہوں؟","roman_urdu":"Hello! Bataiye, main aapki kya help kar sakti hoon?","en":"Hello! How can I help you?"}.get(lang, "Hello! How can I help?")
        if intent == "identity":
            return {"roman_urdu":"Main Alexa hoon, aapki conversational assistant.","ur":"میں Alexa ہوں، آپ کی گفتگو کرنے والی اسسٹنٹ۔"}.get(lang, "I'm Alexa, your conversational assistant.")
        if intent == "thanks":
            return {"roman_urdu":"Khushi hui! Aur kuch poochna ho to bataiye.","ur":"خوشی ہوئی! مزید کچھ پوچھنا ہو تو بتائیے۔"}.get(lang, "You're welcome! Let me know if you need anything else.")
        return {"roman_urdu":"Aapki baat samajh aayi. Is sawal ka behtar jawab dene ke liye thori aur detail dein.","ur":"آپ کی بات سمجھ آئی۔ بہتر جواب کے لیے تھوڑی مزید تفصیل دیں۔"}.get(lang, "I understand. Could you share a little more detail so I can answer accurately?")
