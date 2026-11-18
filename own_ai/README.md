# Alexa Own AI V7.2 — self-hosted conversational service

This is the existing Alexa Own AI service inside the Alexa0.2Music repository. It is not a second bot or a replacement repository.

## Runtime

- Local inference by default using the official Apache-2.0 Qwen3 4B GGUF model.
- Model weights are downloaded from Hugging Face on first inference and cached locally.
- CPU-only llama.cpp inference; memory-conscious defaults are 1 thread, 2K context, 64-token batch, and 256 output tokens.
- Optional OpenAI-compatible remote provider remains supported and takes priority when configured.
- SQLite conversation history, per-user saved-name memory, and explicit feedback preferences.
- Urdu script, Roman Urdu and English handling.
- FastAPI endpoints: GET /, GET /health, POST /chat, POST /v1/chat/completions, POST /feedback.
- Optional bearer-token protection via ALEXA_OWN_AI_TOKEN.

## EthioDeploy

The repository includes a Procfile and Nixpacks start configuration. Deploy this existing repository with the service root set to the repository root.

Start command:
`uvicorn own_ai.main:app --host 0.0.0.0 --port $PORT`

Set these service variables (do not commit secrets):

- `ALEXA_LOCAL_MODEL_ENABLED=true`
- `ALEXA_LOCAL_MODEL_REPO=Qwen/Qwen3-4B-GGUF`
- `ALEXA_LOCAL_MODEL_FILE=Qwen3-4B-Q4_K_M.gguf`
- `ALEXA_LOCAL_MODEL_THREADS=1`
- `ALEXA_LOCAL_MODEL_CONTEXT=2048`
- `ALEXA_LOCAL_MODEL_BATCH=64`
- `ALEXA_LOCAL_MODEL_MAX_TOKENS=256`
- `HF_HOME=/data/huggingface` (only if /data is a persistent writable volume)
- `ALEXA_AI_MEMORY_DB=/data/alexa_own_ai_memory.sqlite3` (only if /data is persistent)
- `ALEXA_AI_LEARNING_DB=/data/alexa_own_ai_learning.sqlite3` (only if /data is persistent)
- `ALEXA_OWN_AI_TOKEN` = a long random secret shared privately with the Telegram bot.

The first startup downloads the public GGUF model (about 1.83 GB) and loads it, so startup can take noticeably longer. The 4B model weights alone need substantially more than 256 MB of RAM; reducing context/batch lowers overhead but cannot make this model fit a 256 MB memory limit. Later requests reuse the cached model. Keep a persistent volume mounted if the host supports one; otherwise model downloads and SQLite data may be lost when the container is recreated.

## FadeHost Telegram bot

Configure the bot to call the deployed service's `/chat` endpoint over HTTPS. Send a stable conversation ID per Telegram chat/user, the Telegram user ID as `user_id`, and the same bearer token in the Authorization header. Never put the token in GitHub source code or public logs.

Example request body:
`{"message":"Tum kese ho?","conversation_id":"telegram:123:456","user_id":"123"}`

## Important limits

The local model is a compact 4B parameter model selected for CPU hosting, not a frontier-scale model. It can converse and follow context, but quality and speed are limited by the model and the host's CPU. No code can guarantee perfect Roman Urdu. The `/health` endpoint reports whether the backend is configured and whether the local model has loaded.

## Local tests

`python -m unittest discover -s own_ai/tests -v`
