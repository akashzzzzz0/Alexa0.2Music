"""Standalone HTTP API for Alexa Own AI. Run: uvicorn own_ai.main:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .chat import AlexaAI

app = FastAPI(title="Alexa Own AI", version="7.0.0")
engine = AlexaAI()
TOKEN = os.getenv("ALEXA_OWN_AI_TOKEN", "")

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str = Field(default="default", max_length=128)

@app.get("/health")
async def health():
    return {"ok": True, "service": "alexa-own-ai", "version": "7.0.0"}

@app.post("/chat")
async def chat(payload: ChatRequest, authorization: str | None = Header(default=None)):
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")
    return await engine.chat(payload.message, payload.conversation_id)

@app.post("/v1/chat/completions")
async def completions(payload: ChatRequest, authorization: str | None = Header(default=None)):
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")
    result = await engine.chat(payload.message, payload.conversation_id)
    return {"choices":[{"index":0,"message":{"role":"assistant","content":result["reply"]},"finish_reason":"stop"}],"model":"alexa-own-ai-v7"}
