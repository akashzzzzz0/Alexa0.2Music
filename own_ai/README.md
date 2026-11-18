# Alexa Own AI V7

A modular conversational engine separated from the Telegram Music Bot.

## Modules
- `chat.py`: conversation orchestration
- `understanding.py`: intent and context parsing
- `reasoning.py`: bounded response planning
- `language.py`: Urdu, Roman Urdu and English detection
- `personality.py`: Alexa voice/style layer
- `reply.py`: response composition
- `memory.py`: bounded in-process conversation context
- `learning.py`: explicit feedback preference counters
- `main.py`: FastAPI service

## Run
Install with `pip install -r own_ai/requirements.txt`, then run:
`uvicorn own_ai.main:app --host 0.0.0.0 --port 8000`

Optional authentication: set `ALEXA_OWN_AI_TOKEN`. Send it as `Authorization: Bearer <token>`.

Endpoints: `GET /health`, `POST /chat`, and `POST /v1/chat/completions`.

This is a clean modular foundation, not a trained foundation model. A language-model provider must be connected through the responder interface for open-domain knowledge and deeper answers. Memory and feedback learning are in-process and reset on restart.
