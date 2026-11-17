# Alexa Own AI — low-memory multilingual assistant

A dependency-free Python HTTP service for small containers such as a 256 MB class
plan. It uses Python's standard library only: no downloaded model weights, no
third-party AI API calls, and no external provider keys.

## What it can do

- Understand common conversational phrases in English, Roman Urdu, Roman Hindi,
  and Roman Punjabi.
- Accept Urdu-script and Devanagari Hindi input and transliterate it internally.
- Keep replies in English for English input; other supported languages are
  answered in Roman text (never Urdu or Devanagari script).
- Handle greetings, small talk, basic emotional acknowledgements, jokes,
  date/time and safe arithmetic.
- Use the latest twenty messages as context when a stable conversation identifier
  is supplied.
- Store conversation turns in SQLite, separately per conversation.

**Important limitation:** this is an improved offline conversational engine,
not a trained generative language model. It cannot reliably answer arbitrary
factual, technical, current-events, or open-ended questions. Its transliteration
and language detection are lightweight approximations, not full linguistic
models. It should ask for clarification or be honest when it does not know.

## Self-hosted generative model (optional)

To enable genuine generative responses without Gemini/Groq or another third-party
AI provider, run an OpenAI-compatible inference server that you own/control
(for example, a local model server on your own device or private server), then
configure these environment variables on this service:

- `ALEXA_LOCAL_MODEL_URL`: base URL, `/v1`, or full
  `/v1/chat/completions` endpoint for your self-hosted inference server.
- `ALEXA_LOCAL_MODEL_NAME`: model identifier expected by that server (default
  `local-model`).
- `ALEXA_LOCAL_MODEL_TOKEN`: optional bearer token for a protected endpoint.
- `ALEXA_LOCAL_MODEL_TIMEOUT`: request timeout in seconds (default 35; capped at 90).

The adapter sends the recent conversation context and a multilingual Alexa
system prompt. Only `user` and `assistant` history roles are forwarded. If the
model endpoint is unset or unreachable, the existing offline engine answers
instead. The adapter itself does not download model weights or create a hosted
model: the inference server and its compute must be supplied separately. Do not
expose a phone/server inference port publicly without authentication and a
secure private connection.

## API

- `GET /health`
- `POST /chat`
- `POST /v1/chat/completions` (OpenAI-compatible request/response shape)

Example `/chat` request:

```json
{
  "conversation_id": "telegram:chat_id:user_id",
  "message": "Ki haal aa?"
}
```

For durable per-chat memory, the caller should pass a stable, non-secret
`conversation_id` (or `chat_id` and `user_id`) on every request. Without an
identifier, supplied request history can be used for that request, but server
memory cannot be safely separated between users.

If `ALEXA_AI_TOKEN` is set, POST requests require
`Authorization: Bearer <ALEXA_AI_TOKEN>`.

## EthioDeploy setup

- Set the service root directory to `alexa_own_ai` if the deployment UI asks.
- Build with the included Dockerfile or run `python app.py`.
- Use the platform-provided `PORT` value (default is 3000).
- Set `ALEXA_AI_TOKEN` as a secret and use the same value in the bot's
  `ALEXA_OWN_AI_API_KEY` setting.
- Set `ALEXA_AI_DB_PATH` to a file on a persistent volume if EthioDeploy offers
  one. The default is `alexa_memory.sqlite3` in the application directory.
  SQLite data can survive process restarts, but it cannot survive container
  replacement/redeployment unless that path is backed by persistent storage.

The service is intentionally lightweight for a 256 MB environment. A real
generative model needs substantially more RAM and compute. This service does
not silently call Gemini, Groq, or any other external AI provider.

## ZIP artifact

The public repository's **Build Alexa Own AI ZIP** GitHub Actions workflow
packages this folder. Download the artifact from the latest successful run in
the repository's Actions tab.
