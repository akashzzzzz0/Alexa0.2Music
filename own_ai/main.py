"""Alexa Own AI HTTP API with local GGUF inference and OpenAI-compatible chat requests."""
from __future__ import annotations
import asyncio
import logging
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .chat import AlexaAI

app = FastAPI(title="Alexa Own AI", version="7.2.1")
engine = AlexaAI()
TOKEN = os.getenv("ALEXA_OWN_AI_TOKEN", "")
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str = Field(default="default", max_length=128)
    user_id: str | None = Field(default=None, max_length=128)


class OpenAIMessage(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=12000)


class OpenAIChatRequest(BaseModel):
    messages: list[OpenAIMessage] = Field(min_length=1, max_length=64)
    model: str = "auto"
    conversation_id: str = Field(default="default", max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    temperature: float = Field(default=0.65, ge=0, le=2)
    max_tokens: int = Field(default=384, ge=1, le=2048)


class FeedbackRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    preference: str = Field(min_length=1, max_length=80)
    positive: bool = True


def authorize(authorization: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="service bearer token is not configured")
    if authorization != "Bearer " + TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.on_event("startup")
async def warm_local_model_in_background():
    if engine.local_model.configured and not (engine.provider_url and engine.model):
        async def _warm():
            try:
                await asyncio.to_thread(engine.local_model.warmup)
                logger.info("Alexa local GGUF model is loaded and ready")
            except Exception:
                logger.exception("Alexa local GGUF model warmup failed")
        app.state.model_warmup_task = asyncio.create_task(_warm())


@app.get("/")
async def root():
    return {"ok": True, "service": "alexa-own-ai", "health": "/health", "chat": "/chat"}


@app.get("/health")
async def health():
    remote_ready = bool(engine.provider_url and engine.model)
    local_ready = engine.local_model.configured
    return {
        "ok": True,
        "service": "alexa-own-ai",
        "version": "7.2.1",
        "model_configured": remote_ready or local_ready,
        "inference_backend": "remote" if remote_ready else ("local_gguf" if local_ready else "none"),
        "local_model_loaded": engine.local_model.loaded,
        "local_model_state": (
            "ready" if engine.local_model.loaded else
            ("loading" if not getattr(app.state, "model_warmup_task", None) is None
             and not app.state.model_warmup_task.done() else "not_loaded")
        ),
        "auth_enabled": bool(TOKEN),
        "local_model_repo": engine.local_model.repo_id if local_ready else None,
        "memory": "sqlite",
        "learning": "explicit-feedback-sqlite",
    }


@app.post("/chat")
async def chat(payload: ChatRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    try:
        return await engine.chat(payload.message, payload.conversation_id, payload.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/v1/chat/completions")
async def completions(payload: OpenAIChatRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    user_messages = [item.content for item in payload.messages if item.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=422, detail="messages must contain a user message")
    system_prompt = "\n".join(
        item.content for item in payload.messages if item.role == "system"
    )
    try:
        result = await engine.chat(
            user_messages[-1],
            payload.conversation_id,
            payload.user_id or payload.conversation_id,
            system_prompt=system_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": "alexa-chat",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result["reply"]},
            "finish_reason": "stop",
        }],
        "model": payload.model or engine.model or engine.local_model.repo_id,
        "metadata": {
            "language": result["language"],
            "intent": result["intent"],
            "source": result["source"],
        },
    }


@app.post("/feedback")
async def feedback(payload: FeedbackRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine.record_feedback(payload.user_id, payload.preference, payload.positive)
    return {"ok": True, "preferences": engine.learning.preferences(payload.user_id)}
