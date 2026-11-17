# Alexa Own AI — multilingual contextual assistant

A lightweight Python service for Alexa's Own AI. It combines deterministic
conversation handling, structured conversational analysis, SQLite history,
and optional hosted or self-hosted language-model inference.

## Current capabilities

- English, Roman Urdu/Hindi/Punjabi, Urdu-script, and Devanagari input support.
- Recent conversation history stored per stable conversation ID (latest 20
  messages); the model receives a bounded recent window.
- Structured cues for message intent, corrections, follow-ups, tone, and emoji.
  These cues are explicitly heuristic and are checked against the conversation.
- Cloudflare Workers AI as the preferred hosted provider, with an optional
  OpenAI-compatible self-hosted fallback.
- A single overall inference time budget to avoid duplicate slow model calls.
- Deterministic India Standard Time date/time and arithmetic handlers.
- Optional caller-provided context for live application facts, relevant memory,
  and media descriptions/transcripts.

## Hosted model configuration

Cloudflare Workers AI is preferred for the small container. Configure these
variables in EthioDeploy:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` (Workers AI run permission)
- `ALEXA_CLOUDFLARE_MODEL` (optional; defaults to
  `@cf/zai-org/glm-4.7-flash`)
- `ALEXA_LOCAL_MODEL_TIMEOUT` (optional; default 8 seconds)

An optional OpenAI-compatible inference endpoint can be configured with
`ALEXA_LOCAL_MODEL_URL`, `ALEXA_LOCAL_MODEL_NAME`, and
`ALEXA_LOCAL_MODEL_TOKEN`. Cloudflare is attempted first.

## API

- `GET /health`
- `POST /chat`
- `POST /v1/chat/completions`

Example `/chat` request:

```json
{
  "conversation_id": "telegram:chat_id:user_id",
  "message": "Who is first on the chat leaderboard?",
  "context": {
    "group": {"title": "Example group"},
    "leaderboard": [
      {"name": "Gautam", "rank": 1, "messages": 520},
      {"name": "Alex", "rank": 2, "messages": 410}
    ]
  },
  "memory_context": "The user prefers short Roman Urdu replies.",
  "media_context": "Voice transcript: kal group event hai"
}
```

The `context`, `memory_context`, and `media_context` fields are optional.
They are bounded, treated as untrusted reference data (never as instructions),
and are not written into SQLite conversation history. Use them to pass verified
read-only application facts, relevant memory, or text descriptions/transcripts.
For actual live leaderboard or group answers, the calling application must
supply current data in `context`; this service cannot inspect Telegram state
by itself.

### Memory and media limits

The service currently persists the latest 20 text messages per conversation.
Optional memory context is request-scoped; it is not an autonomous long-term
profile store. Image/audio understanding requires the caller to provide a
supported model payload or a trustworthy description/transcript. The default
text chat endpoint does not independently download or interpret Telegram
stickers, images, GIFs, or voice files.

## Security and deployment

- Set `ALEXA_AI_TOKEN` in EthioDeploy and send it as a Bearer token on POST
  requests. Authentication is enforced when configured.
- Never commit API credentials or print them in logs.
- Use a persistent volume for `ALEXA_AI_DB_PATH` if the host supports it;
  SQLite data on an ephemeral container filesystem will not survive replacement.
- Keep the service root directory as `alexa_own_ai`, build with its Dockerfile,
  and leave the start command blank so the image starts `bootstrap.py`.
- Bind to the platform-provided `PORT` (default 3000).

## Validation

The GitHub Actions workflow compiles the service modules and runs the Python
unittest regression suite on changes under `alexa_own_ai/`.
