# Alexa Own AI — multilingual contextual assistant

A lightweight Python service for Alexa's Own AI. It combines deterministic
conversation handling, structured conversational analysis, SQLite history,
and optional hosted or self-hosted language-model inference.

## Current capabilities

- English, Roman Urdu/Hindi/Punjabi, Urdu-script, and Devanagari input support.
- Recent conversation history stored per stable conversation ID (latest 20
  messages); the model receives a bounded recent window.
- Scoped SQLite long-term memory with up to 40 explicit key/value facts per
  memory scope, independent across users/conversations.
- Memory updates, selected-key forgetting, and full-scope forgetting through
  authenticated chat requests; credentials and non-scalar values are rejected.
- Structured cues for message intent, corrections, follow-ups, tone, and emoji.
  These cues are explicitly heuristic and are checked against the conversation.
- Cloudflare Workers AI as the preferred hosted provider, with an optional
  OpenAI-compatible self-hosted fallback.
- A single overall inference time budget to avoid duplicate slow model calls.
- Deterministic India Standard Time date/time and arithmetic handlers.
- Optional caller-provided context for live application facts, relevant memory,
  and media descriptions/transcripts.
- Bounded, dependency-free retrieval of relevant excerpts from caller-extracted
  document text; irrelevant chunks are excluded and document text is treated as
  untrusted reference data.

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

Example `/chat` request (optional document text must be extracted by the caller):

```json
{
  "conversation_id": "telegram:chat_id:user_id",
  "memory_scope": "telegram:user_id",
  "memory_updates": {"reply_language": "Roman Urdu", "reply_style": "short"},
  "message": "Who is first on the chat leaderboard?",
  "context": {
    "group": {"title": "Example group"},
    "leaderboard": [
      {"name": "Gautam", "rank": 1, "messages": 520},
      {"name": "Alex", "rank": 2, "messages": 410}
    ]
  },
  "memory_context": "The user prefers short Roman Urdu replies.",
  "media_context": "Voice transcript: kal group event hai",
  "documents": [
    {"name": "project-notes.txt", "text": "Full extracted text from the attached document"}
  ]
}
```

The `memory_scope` field selects the isolated long-term memory namespace;
if omitted, the conversation ID is used. Keep it stable and user-specific when
the bot should remember an individual across chats (for example
`telegram:user_id`); do not use a shared group ID for personal preferences.

The caller may send `memory_updates` only for facts the user explicitly asked
Alexa to remember or otherwise approved for storage. The service does not
silently infer or auto-save personal facts from ordinary conversation.
Use `forget_memory_keys` to remove selected keys, or
`forget_all_memory: true` to clear the selected memory scope. The /chat
response reports `memory_items`, `memory_saved`, and `memory_deleted`;
the OpenAI-compatible response includes equivalent `x_alexa_memory` metadata.
The `context`, `memory_context`, and `media_context` fields are optional.
The optional `documents` field accepts up to three caller-extracted text
documents (`name` and `text`). The service selects up to four relevant
excerpts for the current question; it does not download Telegram attachments
or parse PDF/DOCX files itself. The Telegram caller must safely extract text
and pass it in this field. Document excerpts are transient and are not saved
to conversation history or long-term memory.
They are bounded, treated as untrusted reference data (never as instructions),
and are not written into SQLite conversation history. Use them to pass verified
read-only application facts, relevant memory, or text descriptions/transcripts.
For actual live leaderboard or group answers, the calling application must
supply current data in `context`; this service cannot inspect Telegram state
by itself.

### Memory and media limits

The service persists the latest 20 text messages per conversation and up to
40 explicit long-term key/value memory items per scope. Long-term memory is
caller-controlled: the bot integration must identify explicit remember/forget
requests and send the corresponding API fields. A stable user-specific
memory_scope is required for cross-chat personal continuity. Image/audio understanding requires the caller to provide a
supported model payload or a trustworthy description/transcript. The default
text chat endpoint does not independently download or interpret Telegram
stickers, images, GIFs, or voice files.

### Conversation intelligence, feedback, and response decisions

- The model prompt now receives a bounded, transient summary of recent turns,
  cautious reference/correction cues, and a consistent Alexa voice profile.
- The feedback API accepts an optional `feedback` object such as
  `{"category":"repetitive","sentiment":"negative"}`. Categories are
  allowlisted; only category, sentiment, scope, and timestamp are stored.
  Raw message text is never stored as feedback. Repeated explicit feedback
  can add guidance to future prompts; this is preference aggregation, not
  model fine-tuning or autonomous code changes.
- The caller may pass `decision_context` with `is_group`, `addressed`,
  `mentioned`, `replied_to`, `bot_name_mentioned`, `username_mentioned`,
  `reply_to_bot`, and `allow_reactions` booleans. For group chats, the caller
  must set an addressing flag only after verifying that the message names or
  mentions Alexa, or replies to Alexa's own message. The response includes a
  decision recommendation: `reply`, `react`, or `silence`.
- For group requests with `is_group: true`, the service recommends `silence`
  unless an explicit addressing flag is true. Silence/reaction decisions return
  an empty assistant reply and do not store a hidden assistant turn. Reactions
  are disabled unless the caller explicitly enables them.
- The Telegram integration must still honor the decision and supply accurate
  addressing flags; this service cannot inspect Telegram messages or send
  Telegram messages/reactions itself. Without group context, the API defaults
  to recommending a reply.

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
