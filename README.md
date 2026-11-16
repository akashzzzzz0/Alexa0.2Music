# Alexa Own AI

This repository now contains the lightweight Alexa Own AI service.

## Deploy on EthioDeploy

- Repository: `akashzzzzz0/Alexa0.2Music`
- Branch: `main`
- Root Directory: `alexa_own_ai`
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile`
- Service Type: Web Service
- Start Command: leave blank (the Dockerfile starts the app)
- Runtime port: `PORT` (defaults to `3000`)

## Endpoints

- `GET /health` — service health
- `GET /` — service information
- `POST /chat` — lightweight chat endpoint
- `POST /v1/chat/completions` — OpenAI-compatible request shape

See [alexa_own_ai/README.md](alexa_own_ai/README.md) for request examples and configuration.

## Important limitation

The current engine is a small offline intent and utility responder, **not a trained large language model**. It can handle only its supported patterns. For open-ended conversation, connect an online model provider in the calling Alexa bot.
