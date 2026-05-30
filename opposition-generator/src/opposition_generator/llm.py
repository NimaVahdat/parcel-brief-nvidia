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


def _messages(prompt: str, system: str | None) -> list[dict]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _backend() -> str:
    """Backend label for error messages."""
    return config.LLM_BASE_URL or config.OLLAMA_URL


def _post_chat(
    messages: list[dict],
    *,
    temperature: float,
    model: str | None,
    json_mode: bool,
    reasoning: bool = True,
) -> str:
    """Return assistant text from the configured backend.

    When ``config.LLM_BASE_URL`` is set, calls the OpenAI-compatible ``/v1/chat/completions``
    (the shared vLLM server); otherwise Ollama's native ``/api/chat``. ``reasoning=False`` sets
    nemotron's ``enable_thinking`` chat-template flag off (no chain-of-thought) — used for
    throwaway/generative tasks (HyDE, letters) to cut latency; the analytical caller keeps it on.
    We don't force ``response_format``: a reasoning model emits its thinking first, so we give a
    generous token budget and fall back to the reasoning channel if ``content`` is empty, then
    ``_parse_json_object`` recovers the JSON. The Ollama path keeps ``format=json``.
    """
    mdl = model or config.LLM_MODEL
    if config.LLM_BASE_URL:
        payload = {
            "model": mdl,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": config.LLM_MAX_TOKENS,
            "stream": False,
        }
        if not reasoning:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
            resp = client.post(
                f"{config.LLM_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer local"},
            )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        if not content:  # reasoning model spent its budget thinking — use the reasoning channel
            content = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
        return content

    payload = {
        "model": mdl,
        "messages": messages,
        "stream": False,
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
        resp = client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def chat(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    model: str | None = None,
    reasoning: bool = True,
) -> str:
    """Single-turn chat completion returning raw text. Raises LLMError on failure."""
    try:
        return _post_chat(
            _messages(prompt, system),
            temperature=temperature,
            model=model,
            json_mode=False,
            reasoning=reasoning,
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError(
            f"LLM backend {_backend()} (model={model or config.LLM_MODEL}) failed: {exc}"
        ) from exc


def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    model: str | None = None,
    reasoning: bool = True,
) -> dict:
    """Chat completion constrained to a JSON object. Retries once, then raises.

    Steers toward JSON (Ollama ``format=json``; the OpenAI path relies on the prompt) and guards
    the parse because models occasionally wrap output in prose or code fences.
    """
    messages = _messages(prompt, system)
    last_err: Exception | None = None
    temp = temperature
    for _ in range(2):
        try:
            return _parse_json_object(
                _post_chat(
                    messages, temperature=temp, model=model, json_mode=True, reasoning=reasoning
                )
            )
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            temp = 0.2  # nudge the model harder on the retry
    raise LLMError(
        f"LLM backend {_backend()} (model={model or config.LLM_MODEL}) returned no valid JSON: {last_err}"
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
