# Alexa Own AI — low-memory local assistant

A dependency-free Python HTTP service intended for very small containers (including
256 MB class plans). It provides a small offline intent/utility engine.

**Honest limitation:** this is not a trained LLM. It supports selected English and
Roman Urdu conversation patterns, greetings, basic small-talk, date/time and safe
arithmetic. It cannot understand arbitrary topics like a modern language model.
Unknown questions receive an honest fallback instead of fabricated answers.

## Endpoints

- \`GET /health\`
- \`POST /chat\` with JSON: \`{"message":"salam","history":[]}\`
- \`POST /v1/chat/completions\` with an OpenAI-compatible \`messages\` array

If \`ALEXA_AI_TOKEN\` is set, POST requests require
\`Authorization: Bearer <ALEXA_AI_TOKEN>\`.

## Deploy on EthioDeploy

- Set the app/root directory to \`alexa_own_ai\` if supported.
- Build with the included Dockerfile, or run \`python app.py\`.
- Set \`PORT\` to the port supplied by the platform.
- Set a long random \`ALEXA_AI_TOKEN\` secret and use the same token in the caller.

## Memory and resource use

The service loads no model weights and uses only Python's standard library.
It processes one request at a time to keep memory use predictable. Conversation
history is accepted from the caller but is not stored on the server. This is
suitable for testing on a 256 MB class plan, subject to the host's own limits.

## Important

This does not remove third-party AI quotas or guarantee uptime. A full generative
model needs substantially more memory. Keep Groq/Gemini/other configured providers
for open-ended answers and use this service only as a lightweight offline fallback.
