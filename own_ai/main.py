"""Alexa Own AI HTTP API. Configure ALEXA_AI_BASE_URL, ALEXA_AI_MODEL and optional API key."""
from __future__ import annotations
import os
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,Field
from .chat import AlexaAI
app=FastAPI(title="Alexa Own AI",version="7.1.0")
engine=AlexaAI()
TOKEN=os.getenv("ALEXA_OWN_AI_TOKEN","")
class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=8000)
    conversation_id:str=Field(default="default",max_length=128)
    user_id:str|None=Field(default=None,max_length=128)
class FeedbackRequest(BaseModel):
    user_id:str=Field(min_length=1,max_length=128)
    preference:str=Field(min_length=1,max_length=80)
    positive:bool=True
def authorize(authorization:str|None):
    if TOKEN and authorization != "Bearer "+TOKEN: raise HTTPException(status_code=401,detail="unauthorized")
@app.get("/health")
async def health():
    return {"ok":True,"service":"alexa-own-ai","version":"7.1.0",
            "model_configured":bool(engine.provider_url and engine.model),
            "memory":"sqlite","learning":"explicit-feedback-sqlite"}
@app.post("/chat")
async def chat(payload:ChatRequest,authorization:str|None=Header(default=None)):
    authorize(authorization)
    try: return await engine.chat(payload.message,payload.conversation_id,payload.user_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc))
@app.post("/v1/chat/completions")
async def completions(payload:ChatRequest,authorization:str|None=Header(default=None)):
    authorize(authorization)
    result=await engine.chat(payload.message,payload.conversation_id,payload.user_id)
    return {"id":"alexa-chat","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":result["reply"]},"finish_reason":"stop"}],"model":engine.model or "alexa-own-ai","metadata":{"language":result["language"],"intent":result["intent"],"source":result["source"]}}
@app.post("/feedback")
async def feedback(payload:FeedbackRequest,authorization:str|None=Header(default=None)):
    authorize(authorization)
    engine.record_feedback(payload.user_id,payload.preference,payload.positive)
    return {"ok":True,"preferences":engine.learning.preferences(payload.user_id)}
