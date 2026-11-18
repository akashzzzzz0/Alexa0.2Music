"""Lazy local GGUF inference for a self-hosted Alexa chat model."""
from __future__ import annotations

import os
import threading
from typing import Any


class LocalGGUFModel:
    """Load one quantized chat model on first use and reuse it."""

    def __init__(self) -> None:
        self.repo_id = os.getenv("ALEXA_LOCAL_MODEL_REPO", "Qwen/Qwen3-4B-GGUF")
        self.filename = os.getenv("ALEXA_LOCAL_MODEL_FILE", "Qwen3-4B-Q4_K_M.gguf")
        self.model_path = os.getenv("ALEXA_LOCAL_MODEL_PATH", "").strip()
        self.enabled = os.getenv("ALEXA_LOCAL_MODEL_ENABLED", "true").strip().lower() not in {
            "0", "false", "no", "off"
        }
        # Keep the KV cache small on low-memory CPU hosts. Can be raised by env.
        self.n_ctx = max(2048, int(os.getenv("ALEXA_LOCAL_MODEL_CONTEXT", "2048")))
        self.n_threads = max(1, int(os.getenv("ALEXA_LOCAL_MODEL_THREADS", "1")))
        self.n_batch = max(32, int(os.getenv("ALEXA_LOCAL_MODEL_BATCH", "64")))
        self.max_tokens = max(64, int(os.getenv("ALEXA_LOCAL_MODEL_MAX_TOKENS", "256")))
        self._model: Any = None
        self._lock = threading.RLock()

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.model_path or (self.repo_id and self.filename))

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError(
                    "Local model runtime is missing. Install llama-cpp-python."
                ) from exc

            options = {
                "n_ctx": self.n_ctx,
                "n_threads": self.n_threads,
                "n_batch": self.n_batch,
                "verbose": False,
            }
            if self.model_path:
                self._model = Llama(model_path=self.model_path, **options)
            else:
                # Public GGUF weights are downloaded once into the Hugging Face cache.
                self._model = Llama.from_pretrained(
                    repo_id=self.repo_id,
                    filename=self.filename,
                    **options,
                )
            return self._model

    def warmup(self) -> None:
        """Download and load the model before the first chat request."""
        self._load()

    def reply(self, messages: list[dict]) -> str:
        with self._lock:
            result = self._load().create_chat_completion(
                messages=messages,
                temperature=0.65,
                top_p=0.85,
                repeat_penalty=1.12,
                max_tokens=self.max_tokens,
            )
        choices = result.get("choices") or []
        if not choices:
            raise RuntimeError("Local model returned no choices.")
        content = (choices[0].get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Local model returned an empty response.")
        return content.strip()
