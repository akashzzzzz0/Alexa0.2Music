# Build with the repository root as the build context and this file as the Dockerfile.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODEL=qwen3:4b \
    ALEXA_AI_ENGINE=ollama \
    ALEXA_AI_BASE_URL=http://127.0.0.1:11434/v1 \
    ALEXA_AI_MODEL=qwen3:4b \
    ALEXA_AI_MEMORY_DB=/data/alexa_memory.sqlite3 \
    ALEXA_AI_LEARNING_DB=/data/alexa_learning.sqlite3

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app
COPY own_ai/requirements.txt /app/own_ai/requirements.txt
RUN pip install -r /app/own_ai/requirements.txt
COPY own_ai/ /app/own_ai/

RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "/app/own_ai/start.sh"]
