"""Optional local GGUF inference; disabled by default on low-memory hosts."""
from __future__ import annotations

import os
import threading
from typing import Any


class LocalGGUFModel:
    """Load one quantized model only when explicitly enabled."""

    def __init__(self) -> None:
        self.repo_id = os.getenv("ALEXA_LOCAL_MODEL_REPO", "Qwen/Qwen3-4B-GGUF")
        self.filename = os.getenv("ALEXA_LOCAL_MODEL_FILE", "Qwen3-4B-Q4_K_M.gguf")
        self.model_path = os.getenv("ALEXA_LOCAL_MODEL_PATH", "").strip()
        # 4B GGUF weights cannot fit in a 256 MB service container.
        # Remote inference is the intended low-memory mode.
        self.enabled = os.getenv("ALEXA_LOCAL_MODEL_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.n_ctx = max(2048, int(os.getenv("ALEXA_LOCAL_MODEL_CONTEXT", "8192")))
        self.n_threads = max(1, int(os.getenv("ALEXA_LOCAL_MODEL_THREADS", "2")))
        self._model: Any = None
        self._lock = threading.RLock()

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.model_path or (self.repo_id and self.filename))

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if not self.configured:
            raise RuntimeError(
                "Local GGUF inference is disabled. Configure ALEXA_AI_BASE_URL and "
                "ALEXA_AI_MODEL for remote inference, or explicitly enable local inference."
            )
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
                "n_batch": 256,
                "verbose": False,
            }
            if self.model_path:
                self._model = Llama(model_path=self.model_path, **options)
            else:
                from huggingface_hub import hf_hub_download

                model_path = hf_hub_download(
                    repo_id=self.repo_id,
                    filename=self.filename,
                )
                self._model = Llama(model_path=model_path, **options)
            return self._model

    def warmup(self) -> None:
        """Load the optional local model before serving requests."""
        self._load()

    def reply(self, messages: list[dict]) -> str:
        with self._lock:
            result = self._load().create_chat_completion(
                messages=messages,
                temperature=0.65,
                top_p=0.85,
                repeat_penalty=1.12,
                max_tokens=384,
            )
        choices = result.get("choices") or []
        if not choices:
            raise RuntimeError("Local model returned no choices.")
        content = (choices[0].get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Local model returned an empty response.")
        return content.strip()
