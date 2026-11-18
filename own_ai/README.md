# Alexa Own AI V7.1 — self-hosted conversational service

A conversational service kept separate from the Telegram Music Bot. The existing memory, language understanding, response planning and Alexa personality modules remain in place.

## Included capabilities
- Urdu-script, Roman Urdu and English detection with mixed-language tolerant heuristics.
- Context extraction and bounded response planning.
- Consistent Alexa assistant persona.
- SQLite conversation memory and explicit user feedback preferences.
- OpenAI-compatible chat-completions client.
- Optional local Ollama engine (no third-party model API key or per-request provider quota).
- FastAPI endpoints: GET /health, POST /chat, POST /v1/chat/completions, POST /feedback.
- Optional bearer-token protection via ALEXA_OWN_AI_TOKEN.

## Self-host with Ollama

The deployment container starts Ollama privately, downloads the configured model on first boot, then starts the Alexa API. The default model is `qwen3:4b`.

Build from the repository root, selecting `own_ai/Dockerfile` as the Dockerfile:

```bash
docker build -f own_ai/Dockerfile -t alexa-own-ai .
docker run -d --name alexa-own-ai \
  -p 8000:8000 \
  -v alexa-own-ai-data:/data \
  -e ALEXA_OWN_AI_TOKEN='replace-with-a-long-random-secret' \
  alexa-own-ai
```

The persistent `/data` volume stores downloaded Ollama model files and SQLite memory. Keep it attached across restarts/deployments. The first startup downloads the model and can take time; later starts reuse the cached model.

### Hosting environment variables
- `OLLAMA_MODEL`: model to download; defaults to `qwen3:4b`.
- `ALEXA_AI_MODEL`: model identifier sent to Ollama; defaults to `OLLAMA_MODEL`.
- `ALEXA_OWN_AI_TOKEN`: strongly recommended long random API access token. Never commit the real token.
- `ALEXA_AI_MEMORY_DB` and `ALEXA_AI_LEARNING_DB`: SQLite paths; defaults point to `/data`.
- `OLLAMA_KEEP_ALIVE`: defaults to `24h`.
- `OLLAMA_NUM_PARALLEL`: defaults to `1` to limit concurrent model execution on modest hosts.
- `PORT`: HTTP API port; defaults to `8000`.

The startup script sets `ALEXA_AI_ENGINE=ollama` and the internal Ollama URL automatically. Ollama listens only on localhost inside the container; expose the Alexa API port, not Ollama's port 11434.

## API

Health check:

```http
GET /health
```

Chat:

```http
POST /chat
Authorization: Bearer YOUR_ALEXA_OWN_AI_TOKEN
Content-Type: application/json

{"message":"Tum kya kar sakti ho?","conversation_id":"telegram:123","user_id":"123"}
```

Feedback:

```http
POST /feedback
Authorization: Bearer YOUR_ALEXA_OWN_AI_TOKEN
Content-Type: application/json

{"user_id":"123","preference":"short_replies","positive":true}
```

## Existing provider mode

For non-Ollama deployments, leave `ALEXA_AI_ENGINE` unset and configure:
- `ALEXA_AI_BASE_URL`: OpenAI-compatible provider base URL ending in `/v1`.
- `ALEXA_AI_MODEL`: exact model identifier.
- `ALEXA_AI_API_KEY`: optional; only set if that provider requires it.

## Important limitations

Self-hosting removes a third-party API's daily message quota and per-message model fee; it does not make compute infinite or hosting free. Throughput and response speed depend on the host's CPU/RAM/GPU and concurrent users. The model is downloaded at first startup, so persistent storage is important. SQLite persistence requires a writable persistent disk; ephemeral disks can be reset. Back up databases before deleting or moving them.

Without a configured model/provider (or an injected responder), the service uses simple multilingual fallback replies; it cannot answer arbitrary factual questions deeply. Language detection and intent parsing are helper modules, not a substitute for the language model. Explicit feedback changes prompt preferences; it does not train model weights.
