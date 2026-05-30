"""Ollama chat client with strict-JSON output and a single retry.

All LLM calls in this component go through `chat_json`, which asks Ollama for a
JSON object (`format=json`), parses it, and retries once on failure. Callers get a
plain dict back or an `LLMError` they can catch to fall back gracefully.
"""

from __future__ import annotations

import json

import httpx

from opposition_generator import config


class LLMError(RuntimeError):
    """Raised when the LLM backend is unreachable or returns unusable output."""


def chat(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    model: str | None = None,
) -> str:
    """Single-turn chat completion returning raw text. Raises LLMError on failure."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    url = f"{config.OLLAMA_URL}/api/chat"
    payload = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    try:
        with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError(f"LLM backend {url} (model={config.LLM_MODEL}) failed: {exc}") from exc


def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    model: str | None = None,
) -> dict:
    """Chat completion constrained to a JSON object. Retries once, then raises.

    Uses Ollama's `format=json` so the model is steered toward valid JSON; we still
    guard the parse because models occasionally wrap output in prose or code fences.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    url = f"{config.OLLAMA_URL}/api/chat"
    payload = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {"temperature": temperature},
    }

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                content = resp.json()["message"]["content"]
            return _parse_json_object(content)
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            # nudge the model harder on the retry
            payload["options"]["temperature"] = 0.2
    raise LLMError(
        f"LLM backend {url} (model={config.LLM_MODEL}) returned no valid JSON: {last_err}"
    )


def _parse_json_object(content: str) -> dict:
    """Parse a JSON object out of model output, tolerating code fences / stray prose."""
    content = content.strip()
    if content.startswith("```"):
        # strip ```json ... ``` fences
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...}
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        obj = json.loads(content[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    return obj
