# Alexa Own AI — Micro fallback service

A separate, dependency-free HTTP service for very small free hosting plans.

**Important:** this first version is a rules-based local intent engine, NOT a trained
LLM and NOT a substitute for Qwen/Llama. It can answer a few common greetings and
small-talk intents locally. For open-ended chat, Alexa must continue using its
configured AI providers (for example Groq/Gemini).

## Endpoints

- `GET /health`
- `POST /chat` with JSON: `{"message":"hello"}`
- `POST /v1/chat/completions` with an OpenAI-style `messages` array

If `ALEXA_AI_TOKEN` is set, POST requests require
`Authorization: Bearer <ALEXA_AI_TOKEN>`.

## Deploy on EthioDeploy

- Set the app/root directory to `alexa_own_ai` if the platform supports it.
- Build using the included Dockerfile, or use start command: `python app.py`.
- Set `PORT` to the port supplied by the platform.
- Optionally set `ALEXA_AI_TOKEN` as a secret environment variable.

## Resource limits

This service uses only Python's standard library and does not load a model file.
That makes it suitable for testing on a 256 MB class plan, subject to platform
limits. It does not create unlimited AI capacity: host sleep, request limits and
availability still apply.

## Next stage

A real small language model needs substantially more memory than this microservice.
Do not download or load a Qwen/Llama model into a 256 MB container. Keep this service
as a basic fallback and use external providers for general responses.
