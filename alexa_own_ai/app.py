"""Low-memory local conversation engine for Alexa.

Dependency-free and designed for small containers. This is a lightweight intent/
utility engine, not a trained language model. It never pretends to know answers
outside its supported intents.
"""
import ast
import datetime as dt
import hmac
import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.getenv("PORT", "8080"))
API_TOKEN = os.getenv("ALEXA_AI_TOKEN", "")
MAX_BODY = 32_000
MAX_HISTORY = 12

def normalize(value):
    value = str(value or "").strip().lower()
    value = value.replace("’", "'").replace("’", "'")
    value = re.sub(r"[^\w\s+*/().%-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()

def has_any(text, phrases):
    return any(p in text for p in phrases)

def safe_math(expression):
    """Evaluate only numeric arithmetic; never execute arbitrary Python."""
    expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    if not re.fullmatch(r"[0-9\s.+\-*/()%]*", expression):
        return None
    try:
        node = ast.parse(expression, mode="eval")
        def calc(n):
            if isinstance(n, ast.Expression):
                return calc(n.body)
            if isinstance(n, ast.Constant) and type(n.value) in (int, float):
                return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                v = calc(n.operand)
                return v if isinstance(n.op, ast.UAdd) else -v
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
                a, b = calc(n.left), calc(n.right)
                if isinstance(n.op, ast.Add): result = a + b
                elif isinstance(n.op, ast.Sub): result = a - b
                elif isinstance(n.op, ast.Mult): result = a * b
                elif isinstance(n.op, ast.Div): result = a / b
                elif isinstance(n.op, ast.FloorDiv): result = a // b
                elif isinstance(n.op, ast.Mod): result = a % b
                else:
                    if abs(b) > 8: raise ValueError()
                    result = a ** b
                if abs(result) > 10**15: raise ValueError()
                return result
            raise ValueError()
        result = calc(node)
        if not math.isfinite(float(result)):
            return None
        return int(result) if int(result) == result else round(result, 6)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None

def answer(message, history=None):
    raw = str(message or "").strip()
    t = normalize(raw)
    if not t:
        return "Haan, main yahin hoon. Kya baat hai?"

    # Basic arithmetic is useful offline and has no model dependency.
    math_text = re.sub(r"^(what is|calculate|solve|kitna hota hai|btao)\s+", "", t)
    if re.search(r"\d\s*[+*/%\-]\s*\d", math_text) or re.search(r"\d\s*(×|÷|\^)\s*\d", raw):
        result = safe_math(math_text if math_text != t else raw)
        if result is not None:
            return "Iska jawab " + str(result) + " hai."

    if has_any(t, ("good morning", "subha bakhair", "subah bakhair")):
        return "Good morning! Aaj ka din kaisa ja raha hai?"
    if has_any(t, ("good afternoon", "dopahar")):
        return "Good afternoon! Sab theek chal raha hai?"
    if has_any(t, ("good evening", "sham bakhair", "shaam bakhair")):
        return "Good evening! Aaj kya haal hai?"
    if has_any(t, ("good night", "goodnight", "shab bakhair")):
        return "Good night! Apna khayal rakhna."
    if has_any(t, ("assalam o alaikum", "assalamu alaikum", "salam", "asalamualaikum", "السلام علیکم")):
        return "Wa alaikum assalam! Kya haal hain?"
    if re.fullmatch(r"(hi|hii+|hello|helloo+|hey|heyy+|yo|aoa|salam|salaam)[!. ]*", t):
        return "Hey! Kya haal hai? Aaj kya scene hai?"
    if has_any(t, ("how are you", "how r u", "kaise ho", "kaisay ho", "kesi ho", "kese ho", "kya haal")):
        return "Main theek hoon! Tum sunao, sab kaisa chal raha hai?"
    if has_any(t, ("thank you", "thanks", "shukriya", "bohat shukriya", "thx")):
        return "Koi baat nahi! Khushi hui help karke."
    if has_any(t, ("who are you", "tum kon ho", "tum kaun ho", "ap kon", "your name", "naam kya")):
        return "Main Alexa hoon — group ki friendly assistant. Batao, kis cheez mein help chahiye?"
    if has_any(t, ("what can you do", "kya kar sakti", "kya kar sakte", "help me", "madad chahiye")):
        return "Main basic chat, greetings aur simple calculations mein help kar sakti hoon. Mushkil ya latest sawalon ke liye mujhe online AI ki zaroorat hoti hai."
    if has_any(t, ("i am bored", "bore ho raha", "bore ho rahi", "boring")):
        return "Chalo kuch interesting baat karte hain! Tumhein jokes pasand hain ya random interesting facts?"
    if has_any(t, ("tell me a joke", "joke sunao", "koi joke", "make me laugh")):
        return "Teacher: Homework kahan hai? Student: Sir, Google Drive mein save kiya tha… internet nahi tha! 😄"
    if has_any(t, ("i am sad", "feeling sad", "udaas", "pareshan hoon", "tension hai", "mood off")):
        return "Oh, sun kar afsos hua. Agar batana chaho to kya hua? Main sun sakti hoon."
    if has_any(t, ("i am happy", "bohat khush", "so happy", "great news", "khushi")):
        return "Yeh to achi baat hai! 😄 Kya khushkhabri hai?"
    if has_any(t, ("i love you", "love u")):
        return "Aww, that's kind of you! Main Alexa hoon, aur help ke liye yahin hoon. 💛"
    if has_any(t, ("are you real", "kya tum real", "are you ai", "tum ai ho")):
        return "Main Alexa software assistant hoon. Yeh lightweight offline mode hai, is liye har topic ka jawab nahi de sakti."
    if has_any(t, ("time kya", "what time", "current time", "waqt kya")):
        return "Server ka local time " + dt.datetime.now().astimezone().strftime("%I:%M %p") + " hai."
    if has_any(t, ("today date", "aaj date", "date kya", "what date", "aaj ki tareekh")):
        return "Aaj ki tareekh " + dt.datetime.now().astimezone().strftime("%d %B %Y") + " hai."
    if has_any(t, ("bye", "goodbye", "allah hafiz", "khuda hafiz", "see you")):
        return "Allah hafiz! Phir baat hoti hai. Take care!"
    if has_any(t, ("sorry", "maaf karna", "my bad")):
        return "Koi baat nahi, sab theek hai."
    if has_any(t, ("yes", "haan", "han", "yup", "yeah")):
        # Use the last assistant turn only for a tiny amount of conversational continuity.
        if history:
            previous = " ".join(normalize(x.get("content", "")) for x in history[-4:] if isinstance(x, dict))
            if has_any(previous, ("jokes", "joke")):
                return "Theek hai, ek aur suno: Computer thak gaya… kyun ke uske bohat saare tabs khule thay! 😄"
        return "Achha! Batao, aur kya chal raha hai?"
    if has_any(t, ("no", "nahi", "nahin", "nope")) and len(t.split()) <= 3:
        return "Theek hai, koi masla nahi. Kuch aur baat karni hai?"
    return ("Main ne tumhara message samajhne ki koshish ki, lekin is lightweight offline engine ko "
            "is sawal ka bharosemand jawab nahi aata. Full conversation ke liye online AI provider "
            "available hona zaroori hai.")

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if not API_TOKEN:
            return True
        return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + API_TOKEN)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"ok": True, "service": "alexa-own-ai-micro",
                "engine": "local-intent-utility", "is_llm": False, "memory_mode": "stateless"})
        return self.send_json(200, {"service": "alexa-own-ai-micro",
            "endpoints": ["/health", "/chat", "/v1/chat/completions"]})

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        if self.path not in ("/chat", "/v1/chat/completions"):
            return self.send_json(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > MAX_BODY:
                return self.send_json(413, {"error": "request_too_large"})
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid_json"})

        if self.path == "/chat":
            message = str(body.get("message", ""))
            history = body.get("history", [])
            if not isinstance(history, list):
                history = []
            return self.send_json(200, {"reply": answer(message, history[-MAX_HISTORY:]),
                "provider": "alexa-own-ai-micro", "is_llm": False})

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        message = ""
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content", "")
                message = content if isinstance(content, str) else ""
                break
        history = [x for x in messages[-MAX_HISTORY:] if isinstance(x, dict)]
        return self.send_json(200, {
            "id": "alexa-own-ai-micro", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant",
                "content": answer(message, history)}, "finish_reason": "stop"}]
        })

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    print("Alexa Own AI microservice listening on port", PORT, flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
