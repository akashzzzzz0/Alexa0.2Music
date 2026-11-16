"""Tiny local intent engine for Alexa's low-memory hosting fallback.

This is deliberately dependency-free. It is NOT a generative language model.
"""
import json
import os
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "8080"))
API_TOKEN = os.getenv("ALEXA_AI_TOKEN", "")

def reply_for(message: str):
    text = (message or "").strip().lower()
    if not text:
        return "I'm here. What would you like to talk about?"
    if any(x in text for x in ("hi", "hello", "hey", "salam", "assalam")):
        return "Hey! I'm Alexa. How's your day going?"
    if "good morning" in text:
        return "Good morning! Hope your day goes well."
    if any(x in text for x in ("good night", "goodnight")):
        return "Good night! Take care."
    if any(x in text for x in ("thank you", "thanks", "shukriya")):
        return "You're welcome!"
    if any(x in text for x in ("who are you", "your name")):
        return "I'm Alexa, your friendly group assistant."
    if any(x in text for x in ("how are you", "how r u")):
        return "I'm doing well, thanks for asking. How about you?"
    if any(x in text for x in ("bye", "goodbye", "allah hafiz")):
        return "See you later! Take care."
    return "I'm here, but this lightweight mode can't answer that yet. I'll need an online AI provider for a full answer."

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
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + API_TOKEN
        return hmac.compare_digest(supplied, expected)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {
                "ok": True,
                "service": "alexa-own-ai-micro",
                "engine": "rules-based-local-fallback",
                "is_llm": False
            })
        return self.send_json(200, {
            "service": "alexa-own-ai-micro",
            "endpoints": ["/health", "/chat", "/v1/chat/completions"]
        })

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        if self.path not in ("/chat", "/v1/chat/completions"):
            return self.send_json(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 32_000:
                return self.send_json(413, {"error": "request_too_large"})
            body = json.loads(self.rfile.read(size) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid_json"})

        if self.path == "/chat":
            message = str(body.get("message", ""))
            return self.send_json(200, {
                "reply": reply_for(message),
                "provider": "alexa-own-ai-micro",
                "is_llm": False
            })

        messages = body.get("messages", [])
        message = ""
        for item in reversed(messages):
            if item.get("role") == "user":
                message = str(item.get("content", ""))
                break
        return self.send_json(200, {
            "id": "alexa-own-ai-micro",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply_for(message)},
                "finish_reason": "stop"
            }]
        })

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    print("Alexa Own AI microservice listening on port", PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
