"""Start Alexa Own AI with AI-first conversational routing."""
from http.server import ThreadingHTTPServer

import app
try:
    from ai_router import route_response
except ImportError:
    from .ai_router import route_response

app.conversation_respond = route_response

if __name__ == "__main__":
    print("Alexa Own AI microservice listening on port", app.PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", app.PORT), app.Handler).serve_forever()
