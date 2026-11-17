# Alexa Own AI

This repository contains the standalone Alexa Own AI service used by the
Alexa project. The service lives in `alexa_own_ai/` and is deployed separately
from the Telegram bot.

## Deploy on EthioDeploy

- Repository: `akashzzzzz0/Alexa0.2Music`
- Branch: `main` (or the approved release branch)
- Root Directory: `alexa_own_ai`
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile`
- Service Type: Web Service
- Start Command: leave blank (the Dockerfile starts the app)
- Runtime port: `PORT` (defaults to `3000`)

## Endpoints

- `GET /health` — service health
- `GET /` — service information
- `POST /chat` — conversational chat endpoint
- `POST /v1/chat/completions` — OpenAI-compatible request shape

The service supports multilingual conversation, recent SQLite conversation
history, structured understanding cues, optional hosted/self-hosted model
inference, and optional caller-supplied context. See
[`alexa_own_ai/README.md`](alexa_own_ai/README.md) for configuration, request
examples, memory limits, and media/context integration requirements.

## Important integration boundary

The service cannot read Telegram group state, leaderboard rows, or media files
on its own. The calling application must pass current facts through the
optional `context`, `memory_context`, or `media_context` request fields.
Actual image/audio interpretation also requires a compatible model payload or
a trusted transcript/description from the caller.
