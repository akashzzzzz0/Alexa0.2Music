"""Start Alexa Own AI with AI-first conversational routing."""
from http.server import ThreadingHTTPServer

import app
try:
    import model_runtime
    from ai_router import route_response
except ImportError:
    from . import model_runtime
    from .ai_router import route_response


# Keep one consistent Alexa voice for hosted inference without changing the
# provider adapter or requiring additional packages.
_original_messages = model_runtime._messages


def _alexa_messages(message, history, context=None):
    messages = _original_messages(message, history, context=context)
    messages[0]["content"] += (
        " You are Alexa and use a friendly, feminine conversational voice. "
        "In Roman Urdu/Hindi, use natural feminine forms such as 'kar rahi hoon' "
        "when speaking about yourself. Sound like a real-time chat assistant, "
        "not a customer-support script. Match the user's casualness and language; "
        "usually keep chat replies to one or two natural sentences, but give "
        "complete detail when the user asks a real question. Answer the actual "
        "message directly. Use recent turns to resolve 'ye', 'woh', 'uska', "
        "corrections, jokes, and follow-up questions. Do not repeat stock "
        "clarification lines or claim you understood if you did not. Ask at most "
        "one specific question only when needed. Never invent memories, facts, "
        "or real-world experiences; be transparent if asked whether you are AI."
    )
    return messages


model_runtime._messages = _alexa_messages
app.conversation_respond = route_response

if __name__ == "__main__":
    print("Alexa Own AI microservice listening on port", app.PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", app.PORT), app.Handler).serve_forever()
