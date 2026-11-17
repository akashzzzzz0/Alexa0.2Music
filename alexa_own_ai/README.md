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

## Generative model: Cloudflare Workers AI

The service can use Cloudflare-hosted GLM-4.7-Flash for genuine generative
multilingual replies. The model runs on Cloudflare, not inside the small
EthioDeploy container. Configure these environment variables on EthioDeploy:

- `CLOUDFLARE_ACCOUNT_ID`: your Cloudflare account ID.
- `CLOUDFLARE_API_TOKEN`: a secret API token with permission to run Workers AI.
- `ALEXA_CLOUDFLARE_MODEL`: optional model ID; defaults to
  `@cf/zai-org/glm-4.7-flash`.

The adapter sends the multilingual Alexa system prompt and recent conversation
context to Cloudflare. If Cloudflare credentials are absent or the request fails,
it tries the optional self-hosted endpoint below, then the offline conversation
engine. Never put Cloudflare credentials in source code or share them publicly.

### Optional self-hosted model

For an OpenAI-compatible inference server that you operate, configure:

- `ALEXA_LOCAL_MODEL_URL`: base URL, `/v1`, or full
  `/v1/chat/completions` endpoint.
- `ALEXA_LOCAL_MODEL_NAME`: exact model identifier expected by that server.
- `ALEXA_LOCAL_MODEL_TOKEN`: optional bearer token.
- `ALEXA_LOCAL_MODEL_TIMEOUT`: timeout in seconds (default 35; capped at 90).

The local adapter does not download model weights or create a hosted model.

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
- Keep `ALEXA_AI_TOKEN` as a secret and use the same value in the bot's
  `ALEXA_OWN_AI_API_KEY` setting. This protects the Alexa microservice API.
- Add `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` as separate secrets
  to enable the hosted GLM model. The existing `ALEXA_AI_TOKEN` is not a
  Cloudflare model credential.
- Optionally set `ALEXA_CLOUDFLARE_MODEL` to
  `@cf/zai-org/glm-4.7-flash`; this is also the built-in default.
- Set `ALEXA_AI_DB_PATH` to a file on a persistent volume if EthioDeploy offers
  one. The default is `alexa_memory.sqlite3` in the application directory.
  SQLite data can survive process restarts, but it cannot survive container
  replacement/redeployment unless that path is backed by persistent storage.

The service remains lightweight for a 256 MB environment because inference is
performed by Cloudflare when configured. Cloudflare usage may be subject to
account limits and pricing. Without Cloudflare credentials or a working local
model endpoint, the offline conversational engine remains active.

## ZIP artifact

The public repository's **Build Alexa Own AI ZIP** GitHub Actions workflow
packages this folder. Download the artifact from the latest successful run in
the repository's Actions tab.
