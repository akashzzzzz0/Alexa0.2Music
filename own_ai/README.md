# Alexa Own AI V7.3 — Cloudflare chat service

This is the existing Alexa Own AI service inside the Alexa0.2Music repository. It uses Cloudflare Workers AI for chat inference and retains the existing SQLite conversation memory, saved-name memory, and explicit-feedback learning.

## Runtime

- Cloudflare Workers AI through its OpenAI-compatible chat completions API.
- No local GGUF model, Qwen weights, llama.cpp runtime, or model download.
- SQLite conversation history, per-user saved-name memory, and explicit feedback preferences.
- Urdu script, Roman Urdu and English handling.
- FastAPI endpoints: GET /, GET /health, POST /chat, POST /v1/chat/completions, POST /feedback.
- Optional Alexa service bearer-token protection via ALEXA_OWN_AI_TOKEN.

## EthioDeploy configuration

Start command:

`uvicorn own_ai.main:app --host 0.0.0.0 --port $PORT`

Set these environment variables in the hosting dashboard (never commit secrets):

- `ALEXA_AI_BASE_URL=https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1`
- `ALEXA_AI_MODEL=@cf/meta/llama-3.1-8b-instruct`
- `ALEXA_AI_API_KEY=<Cloudflare Workers AI API token>`
- `ALEXA_AI_TIMEOUT=180`
- `ALEXA_OWN_AI_TOKEN=<existing shared secret used by the Telegram bot>`

Keep the existing SQLite database path/volume configuration unchanged. Do not delete or reset the SQLite files when redeploying.

## Health check

`/health` reports `inference_backend=remote` when the Cloudflare endpoint and model are configured. It reports the local model as disabled because this build has no local inference engine.

## Telegram bot

Configure the bot to call the deployed service's `/chat` endpoint over HTTPS. Send a stable conversation ID per Telegram chat/user, the Telegram user ID as `user_id`, and the same Alexa service bearer token in the Authorization header. This is separate from the Cloudflare API token.

Never put either token in GitHub source code or public logs.
