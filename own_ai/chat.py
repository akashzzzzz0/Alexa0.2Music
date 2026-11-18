"""Provider-ready chat orchestration with durable memory and explicit feedback."""
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
    def __init__(self,responder=None):
        self.memory=ConversationMemory()
        self.learning=FeedbackLearning()
        self.responder=responder
        self.provider_url=os.getenv("ALEXA_AI_BASE_URL","").rstrip("/")
        self.provider_key=os.getenv("ALEXA_AI_API_KEY","")
        self.model=os.getenv("ALEXA_AI_MODEL","")
        self.timeout=float(os.getenv("ALEXA_AI_TIMEOUT","45"))
    async def _provider_reply(self,message,history,parsed,plan,user_id):
        if not (self.provider_url and self.model): return None
        headers={"Content-Type":"application/json"}
        if self.provider_key: headers["Authorization"]="Bearer "+self.provider_key
        prefs=self.learning.preferences(user_id)
        system=system_personality()+"\nDetected language: "+parsed["language"]+".\nResponse plan: "+str(plan)+".\nUser feedback preferences (scores): "+str(prefs)+"."
        messages=[{"role":"system","content":system}]
        messages.extend(history[-24:])
        messages.append({"role":"user","content":message})
        url=self.provider_url
        if not url.endswith("/chat/completions"): url += "/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response=await client.post(url,headers=headers,json={"model":self.model,"messages":messages,"temperature":0.7})
            response.raise_for_status()
            data=response.json()
        return data["choices"][0]["message"]["content"]
    async def chat(self,message: str,conversation_id: str="default",user_id: str|None=None) -> dict:
        message=(message or "").strip()
        if not message: raise ValueError("message cannot be empty")
        cid=str(conversation_id)[:128]; uid=str(user_id or cid)[:128]
        history=self.memory.get(cid)
        parsed=understand(message,history)
        prefs=self.learning.preferences(uid)
        plan=build_plan(message,parsed,history,prefs)
        try:
            if self.responder:
                result=self.responder(message=message,history=history,understanding=parsed,plan=plan,preferences=prefs)
                if hasattr(result,"__await__"): result=await result
                answer=str(result)
                source="custom_responder"
            else:
                answer=await self._provider_reply(message,history,parsed,plan,uid)
                source="configured_model" if answer else "fallback"
        except (httpx.HTTPError,KeyError,ValueError) as exc:
            answer=self._fallback(parsed)
            source="fallback"
            error=type(exc).__name__
        else:
            error=None
        answer=compose_reply(answer,parsed["language"])
        self.memory.add(cid,"user",message); self.memory.add(cid,"assistant",answer)
        return {"reply":answer,"language":parsed["language"],"intent":parsed["intent"],
                "source":source,"plan":plan,"provider_error":error}
    def record_feedback(self,user_id: str,preference: str,positive: bool=True):
        self.learning.record(user_id,preference,positive)
    @staticmethod
    def _fallback(parsed: dict) -> str:
        lang,intent=parsed["language"],parsed["intent"]
        answers={
         "greeting":{"ur":"وعلیکم السلام! بتائیں، میں آپ کی کیا مدد کر سکتی ہوں؟","roman_urdu":"Hello! Bataiye, main aapki kya help kar sakti hoon?","en":"Hello! How can I help you?"},
         "identity":{"ur":"میں Alexa ہوں، آپ کی گفتگو کرنے والی اسسٹنٹ۔","roman_urdu":"Main Alexa hoon, aapki conversational assistant.","en":"I'm Alexa, your conversational assistant."},
         "thanks":{"ur":"خوشی ہوئی! مزید کچھ پوچھنا ہو تو بتائیے۔","roman_urdu":"Khushi hui! Aur kuch poochna ho to bataiye.","en":"You're welcome!"},
         "goodbye":{"ur":"اللہ حافظ! جب بھی مدد چاہیے ہو، بتائیے۔","roman_urdu":"Allah hafiz! Jab bhi help chahiye ho, bataiye.","en":"Goodbye! Take care."},
         "help":{"ur":"ضرور، بتائیے کس چیز میں مدد چاہیے؟","roman_urdu":"Zaroor, bataiye kis cheez mein help chahiye?","en":"Of course. What would you like help with?"}}
        return answers.get(intent,{}).get(lang,{"ur":"آپ کی بات سمجھ آئی۔ بہتر جواب کے لیے تھوڑی مزید تفصیل بتائیں۔","roman_urdu":"Aapki baat samajh aayi. Behtar jawab ke liye thori detail dein.","en":"I understand. Could you share a little more detail so I can answer accurately."}.get(lang,"I understand. Could you share a little more detail?"))
