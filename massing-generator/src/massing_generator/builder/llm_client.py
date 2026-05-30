"""
Pluggable LLM client.

One small interface (`LLMClient.generate`) so the spec generator does not care
which backend produces the text. Today: Anthropic Claude. Tomorrow: a custom /
self-hosted model — implement `generate()` in a new subclass and register it in
`get_client()`. NVIDIA NIM, vLLM, TGI, and most local servers expose an
OpenAI-compatible API, so the `OpenAICompatClient` stub below is the usual path.

Usage:
    from llm_client import get_client
    client = get_client("anthropic")          # or "custom"
    text = client.generate(system, messages)  # messages: [{"role","content"}]
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Return assistant text for one completion. Stateless; caller owns history."""

    name = "base"

    @abstractmethod
    def generate(self, system, messages: list[dict], max_tokens: int = 16000) -> str:
        """`system` is a string or a list of content blocks (for cache control).
        `messages` is the running [{"role","content"}] list. Returns text only."""
        raise NotImplementedError


class AnthropicClient(LLMClient):
    """Claude via the official Anthropic SDK.

    Adaptive thinking + high effort (good for the design reasoning this task
    needs). Streams so large specs don't trip the SDK's non-stream timeout.
    `system` blocks carry cache_control upstream, so the big stable schema +
    few-shot prefix is cached across the repair loop and across runs.
    """

    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8"):
        try:
            import anthropic
        except ModuleNotFoundError as e:
            raise SystemExit(
                "anthropic SDK not installed. Run: pip install anthropic\n"
                "(and set ANTHROPIC_API_KEY)"
            ) from e
        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def generate(self, system, messages: list[dict], max_tokens: int = 16000) -> str:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
        ) as stream:
            msg = stream.get_final_message()
        return "".join(b.text for b in msg.content if b.type == "text")


class OpenAICompatClient(LLMClient):
    """Stub for a custom / self-hosted model behind an OpenAI-compatible API
    (NVIDIA NIM, vLLM, TGI, Ollama, ...). Fill in when you wire up the custom LLM.

    Pattern:
        from openai import OpenAI
        self._client = OpenAI(base_url=os.environ["LLM_BASE_URL"],
                              api_key=os.getenv("LLM_API_KEY", "EMPTY"))
        # in generate(): prepend system as a {"role":"system"} message, call
        # self._client.chat.completions.create(model=self.model, messages=...)
        # and return resp.choices[0].message.content
    """

    name = "custom"

    def __init__(self, model: str | None = None):
        # Local Ollama on the GB10 (native /api/chat) — keeps inference on-box,
        # matching the rest of the system. No external API, no key.
        self.base = (os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("MASSING_LLM_MODEL") or os.getenv(
            "LLM_MODEL", "qwen3.6:35b"
        )
        self.timeout = float(os.getenv("MASSING_LLM_TIMEOUT_S", "600"))

    def generate(self, system, messages: list[dict], max_tokens: int = 16000) -> str:
        import httpx

        # `system` may be a string or a list of Anthropic-style content blocks;
        # flatten to plain text for the local chat API.
        if isinstance(system, str):
            sys_text = system
        else:
            sys_text = "\n".join(
                b.get("text", "") for b in (system or []) if isinstance(b, dict)
            )
        msgs = ([{"role": "system", "content": sys_text}] if sys_text else []) + [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.3, "num_predict": max_tokens, "num_ctx": 16384},
        }
        with httpx.Client(timeout=self.timeout) as c:
            resp = c.post(f"{self.base}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]


def get_client(provider: str = "anthropic", model: str | None = None) -> LLMClient:
    provider = (provider or "anthropic").lower()
    if provider == "anthropic":
        return AnthropicClient(model or "claude-opus-4-8")
    if provider in ("custom", "openai", "nim"):
        return OpenAICompatClient(model)
    raise ValueError(f"unknown provider '{provider}' (use: anthropic | custom)")
