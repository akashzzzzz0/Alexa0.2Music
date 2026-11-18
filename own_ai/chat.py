"""Cloudflare-backed chat orchestration with SQLite memory and feedback."""
from __future__ import annotations
import os
import httpx
from .memory import ConversationMemory
from .learning import FeedbackLearning
from .understanding import understand
from .reasoning import build_plan
from .reply import compose_reply
from .personality import system_personality


class AlexaAI:
    def __init__(self, responder=None):
        self.memory = ConversationMemory()
        self.learning = FeedbackLearning()
        self.responder = responder
        self.provider_url = os.getenv("ALEXA_AI_BASE_URL", "").rstrip("/")
        self.provider_key = os.getenv("ALEXA_AI_API_KEY", "")
        self.model = os.getenv("ALEXA_AI_MODEL", "")
        self.timeout = float(os.getenv("ALEXA_AI_TIMEOUT", "180"))

    def _build_messages(self, message, history, parsed, plan, user_id, saved_name=None, external_system_prompt=""):
        prefs = self.learning.preferences(user_id)
        profile = (
            f"Verified saved user name: {saved_name}. Use it naturally when relevant; never invent or alter it."
            if saved_name else "No verified user name is saved. Do not guess the user's name."
        )
        system = (
            system_personality()
            + "\n"
            + profile
            + "\nDetected language: "
            + parsed["language"]
            + ". Match this language and script. For Roman Urdu, use natural Pakistani Roman Urdu; "
              "do not translate it into formal English or produce mixed random words."
            + "\nResponse plan: "
            + str(plan)
            + ".\nUser feedback preferences: "
            + str(prefs)
            + ".\nUse prior messages to understand follow-up questions. Answer the latest user message directly. "
              "Do not repeat greetings unnecessarily. /no_think"
        )
        if external_system_prompt:
            system += "\nTelegram bot persona and conversation instructions:\n" + external_system_prompt[:12000]
        messages = [{"role": "system", "content": system}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})
        return messages

    async def _provider_reply(self, messages):
        if not (self.provider_url and self.model):
            raise RuntimeError("Cloudflare AI is not configured.")
        headers = {"Content-Type": "application/json"}
        if self.provider_key:
            headers["Authorization"] = "Bearer " + self.provider_key
        url = self.provider_url
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=headers,
                json={"model": self.model, "messages": messages, "temperature": 0.55},
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _memory_reply(intent, name, language):
        if intent == "name_recall":
            if name:
                return {
                    "roman_urdu": f"Tumhara naam {name} hai! Mujhe yaad hai.",
                    "ur": f"آپ کا نام {name} ہے، مجھے یاد ہے۔",
                    "en": f"Your name is {name}. I remember.",
                }.get(language, f"Your name is {name}.")
            return {
                "roman_urdu": "Tumne abhi tak mujhe apna naam nahi bataya.",
                "ur": "آپ نے ابھی تک مجھے اپنا نام نہیں بتایا۔",
                "en": "You haven't told me your name yet.",
            }.get(language, "You haven't told me your name yet.")
        if intent == "memory_reason":
            if name:
                return {
                    "roman_urdu": "Kyunki tumne pehle mujhe apna naam bataya tha, aur maine use tumhari profile memory mein save kiya tha.",
                    "ur": "کیونکہ آپ نے پہلے مجھے اپنا نام بتایا تھا، اور میں نے اسے آپ کی پروفائل میموری میں محفوظ کیا تھا۔",
                    "en": "Because you told me your name earlier, and I saved it in your profile memory.",
                }.get(language)
            return {
                "roman_urdu": "Mujhe is waqt tumhara koi saved naam nahi mil raha, isliye main andaza nahi lagaungi.",
                "ur": "مجھے اس وقت آپ کا کوئی محفوظ نام نہیں مل رہا، اس لیے میں اندازہ نہیں لگاؤں گی۔",
                "en": "I don't have a saved name for you yet, so I won't guess.",
            }.get(language)
        return None

    async def chat(self, message: str, conversation_id: str = "default", user_id: str | None = None, system_prompt: str = "") -> dict:
        message = (message or "").strip()
        if not message:
            raise ValueError("message cannot be empty")
        cid, uid = str(conversation_id)[:128], str(user_id or conversation_id)[:128]
        history = self.memory.get(cid)
        parsed = understand(message, history)
        if parsed.get("extracted_name"):
            self.memory.save_name(uid, parsed["extracted_name"])
        saved_name = self.memory.get_name(uid)
        plan = build_plan(message, parsed, history, self.learning.preferences(uid))
        direct = self._memory_reply(parsed["intent"], saved_name, parsed["language"])

        if direct is not None:
            answer, source, error = direct, "profile_memory", None
        elif parsed.get("address_only"):
            if parsed["language"] == "roman_urdu":
                answer = f"Haan {saved_name}, bolo. Kya baat hai?" if saved_name else "Haan, bolo. Kya baat hai?"
            else:
                answer = f"جی {saved_name}، بتائیں؟" if saved_name else "جی، بتائیے؟"
            source, error = "context_fallback", None
        else:
            messages = self._build_messages(message, history, parsed, plan, uid, saved_name, system_prompt)
            try:
                if self.responder:
                    result = self.responder(
                        message=message, history=history, understanding=parsed, plan=plan
                    )
                    if hasattr(result, "__await__"):
                        result = await result
                    answer, source = str(result), "custom_responder"
                else:
                    answer = await self._provider_reply(messages)
                    source = "cloudflare_workers_ai"
                error = None
                if not answer:
                    answer, source = self._fallback(parsed), "fallback"
            except Exception as exc:
                answer, source, error = self._fallback(parsed), "fallback", type(exc).__name__

        answer = compose_reply(answer, parsed["language"])
        self.memory.add(cid, "user", message)
        self.memory.add(cid, "assistant", answer)
        return {
            "reply": answer,
            "language": parsed["language"],
            "intent": parsed["intent"],
            "source": source,
            "plan": plan,
            "provider_error": error,
        }

    def record_feedback(self, user_id: str, preference: str, positive: bool = True):
        self.learning.record(user_id, preference, positive)

    @staticmethod
    def _fallback(parsed: dict) -> str:
        lang, intent = parsed["language"], parsed["intent"]
        answers = {
            "greeting": {
                "ur": "وعلیکم السلام! بتائیں، میں آپ کی کیا مدد کر سکتی ہوں؟",
                "roman_urdu": "Hello! Bataiye, main aapki kya help kar sakti hoon?",
                "en": "Hello! How can I help you?",
            },
            "identity": {
                "ur": "میں Alexa ہوں، آپ کی گفتگو کرنے والی اسسٹنٹ۔",
                "roman_urdu": "Main Alexa hoon, aapki conversational assistant.",
                "en": "I'm Alexa, your conversational assistant.",
            },
            "thanks": {
                "ur": "خوشی ہوئی! مزید کچھ پوچھنا ہو تو بتائیے۔",
                "roman_urdu": "Khushi hui! Aur kuch poochna ho to bataiye.",
                "en": "You're welcome!",
            },
            "goodbye": {
                "ur": "اللہ حافظ! جب بھی مدد چاہیے ہو، بتائیے۔",
                "roman_urdu": "Allah hafiz! Jab bhi help chahiye ho, bataiye.",
                "en": "Goodbye! Take care.",
            },
            "help": {
                "ur": "ضرور، بتائیے کس چیز میں مدد چاہیے؟",
                "roman_urdu": "Zaroor, bataiye kis cheez mein help chahiye?",
                "en": "Of course. What would you like help with?",
            },
        }
        default = {
            "ur": "آپ کی بات سمجھ آئی۔ بہتر جواب کے لیے تھوڑی مزید تفصیل بتائیں۔",
            "roman_urdu": "Aapki baat samajh aayi. Behtar jawab ke liye thori detail dein.",
            "en": "I understand. Could you share a little more detail?",
        }
        return answers.get(intent, default).get(lang, default["en"])
