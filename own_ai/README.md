# Alexa Own AI V7.1 — modular conversational service

A provider-ready conversation service kept separate from the Telegram Music Bot.

## Capabilities
- Urdu-script, Roman Urdu and English detection with mixed-language tolerant heuristics.
- Intent/context extraction and a bounded response plan (no private chain-of-thought is stored).
- Consistent Alexa feminine assistant persona prompt.
- SQLite conversation memory, bounded per conversation and retained across restarts.
- Explicit user feedback preferences persisted in SQLite. These are prompt hints, not model-weight training.
- Optional OpenAI-compatible chat-completions provider.
- FastAPI endpoints: GET /health, POST /chat, POST /v1/chat/completions, POST /feedback.
- Optional bearer-token protection via ALEXA_OWN_AI_TOKEN.

## Configure a real language model
Set these variables in your hosting dashboard; never commit secrets:
- ALEXA_AI_BASE_URL: provider base URL, e.g. https://provider.example/v1
- ALEXA_AI_MODEL: exact model identifier supplied by provider
- ALEXA_AI_API_KEY: provider key (optional only if provider requires no key)
- ALEXA_OWN_AI_TOKEN: your own service access token
- ALEXA_AI_MEMORY_DB and ALEXA_AI_LEARNING_DB: optional SQLite paths on persistent storage

Install: pip install -r own_ai/requirements.txt
Run: uvicorn own_ai.main:app --host 0.0.0.0 --port 8000

## Important limitations
Without ALEXA_AI_BASE_URL and ALEXA_AI_MODEL (or an injected responder), the service uses simple multilingual fallback replies; it cannot answer arbitrary factual questions deeply. Language detection and intent parsing are heuristic helpers, not a substitute for a language model. Feedback preferences do not train model weights. SQLite persistence requires a writable persistent disk; ephemeral hosting disks may be reset. Back up databases before deleting or moving them.

## API examples
POST /chat: {"message":"Tum kya kar sakti ho?","conversation_id":"telegram:123","user_id":"123"}
POST /feedback: {"user_id":"123","preference":"short_replies","positive":true}
