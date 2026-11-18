#!/bin/sh
set -eu

# Keep Ollama private to this container; only the Alexa HTTP API is exposed.
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/data/ollama/models}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-24h}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:4b}"

export ALEXA_AI_ENGINE="ollama"
export ALEXA_AI_BASE_URL="http://127.0.0.1:11434/v1"
export ALEXA_AI_MODEL="${ALEXA_AI_MODEL:-$OLLAMA_MODEL}"
export ALEXA_AI_MEMORY_DB="${ALEXA_AI_MEMORY_DB:-/data/alexa_memory.sqlite3}"
export ALEXA_AI_LEARNING_DB="${ALEXA_AI_LEARNING_DB:-/data/alexa_learning.sqlite3}"

mkdir -p /data "$OLLAMA_MODELS"

ollama serve &
OLLAMA_PID=$!
API_PID=""

cleanup() {
    if [ -n "$API_PID" ]; then kill "$API_PID" 2>/dev/null || true; fi
    kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Waiting for local Ollama..."
until ollama list >/dev/null 2>&1; do
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "Ollama exited before becoming ready." >&2
        exit 1
    fi
    sleep 2
done

echo "Ensuring model is available: $OLLAMA_MODEL"
ollama pull "$OLLAMA_MODEL"

echo "Starting Alexa Own AI API..."
uvicorn own_ai.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
API_PID=$!
wait "$API_PID"
