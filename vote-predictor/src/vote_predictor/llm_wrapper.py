"""The local reasoning model: nemotron-3-super served by Ollama on the GB10.

Thin, reasoning-safe primitives over a local OpenAI-compatible endpoint. Everything runs
locally (``config.LLM_BASE_URL``); no external API is called, per the project's unit
economics. A vLLM FP8 endpoint is a supported stricter-JSON fallback.

**Reasoning-model gotcha (handled here).** nemotron-3-super streams its chain-of-thought
into a separate ``message.reasoning`` field and only then writes the answer into
``message.content``. With too small a token budget it spends everything on reasoning and
``content`` comes back empty. So every call uses a generous ``max_tokens`` and, if
``content`` is empty, falls back to the ``reasoning`` field and strips any ``<think>`` block
before extracting JSON.
"""

from __future__ import annotations

import functools
import json
import re

from vote_predictor import config

#: Matches a ``<think>...</think>`` chain-of-thought block (some models inline it in content).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


@functools.lru_cache(maxsize=1)
def _client():
    """Construct (once) an OpenAI-compatible client pointed at the local endpoint.

    Cached so the panel's chunked per-roster calls reuse one client / connection pool.

    Returns:
        openai.OpenAI: A client configured for ``config.LLM_BASE_URL`` with the local key.

    Raises:
        ImportError: If the ``openai`` package is not installed.
    """
    from openai import OpenAI

    return OpenAI(
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        timeout=config.LLM_TIMEOUT_S,
        max_retries=1,
    )


def _message_text(response) -> str:
    """Extract the usable text from a chat completion, surviving the reasoning-model gotcha.

    Prefers ``message.content``; if that is empty (the model spent its budget in the
    reasoning channel), falls back to ``message.reasoning`` / ``message.reasoning_content``.
    Strips any inline ``<think>`` block either way.

    Args:
        response: An OpenAI-compatible chat completion response object.

    Returns:
        str: The best-available assistant text, or an empty string if none is present.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError):
        return ""
    content = (getattr(message, "content", None) or "").strip()
    if not content:
        content = (
            getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None) or ""
        ).strip()
    return _THINK_RE.sub("", content).strip()


def _extract_json(text: str) -> dict:
    """Extract the first balanced JSON object from a text blob.

    Tolerant of prose or stray tokens around the JSON (e.g. residual reasoning), which a
    reasoning model occasionally emits despite a JSON response format.

    Args:
        text (str): Text that should contain a JSON object.

    Returns:
        dict: The parsed object, or ``{}`` if no parseable object is found.
    """
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : i + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}


def chat_json(
    messages: list[dict], *, max_tokens: int | None = None, temperature: float = 0.0
) -> dict:
    """Call the local model and return a parsed JSON object, reasoning-safe.

    Args:
        messages (list[dict]): OpenAI-style chat messages (system/user/assistant).
        max_tokens (int | None): Completion budget; defaults to ``config.REASONING_MAX_TOKENS``
            (large, so the reasoning channel does not starve ``content``).
        temperature (float): Sampling temperature; 0 for deterministic structured output.

    Returns:
        dict: The parsed JSON object, or ``{}`` if the response is empty/unparseable.

    Raises:
        ImportError: If the ``openai`` package is not installed.
        Exception: Propagates transport errors so the caller can fall back.
    """
    response = _client().chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens or config.REASONING_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    return _extract_json(_message_text(response))


def chat_text(
    messages: list[dict], *, max_tokens: int | None = None, temperature: float = 0.0
) -> str:
    """Call the local model and return plain text, reasoning-safe.

    Args:
        messages (list[dict]): OpenAI-style chat messages.
        max_tokens (int | None): Completion budget; defaults to ``config.REASONING_MAX_TOKENS``.
        temperature (float): Sampling temperature.

    Returns:
        str: The assistant text (empty string if none).

    Raises:
        ImportError: If the ``openai`` package is not installed.
        Exception: Propagates transport errors so the caller can fall back.
    """
    response = _client().chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens or config.REASONING_MAX_TOKENS,
    )
    return _message_text(response)


def parse_application_text(text: str) -> dict:
    """Parse free-text application/report prose into Contract 1 feature fields.

    Used to enrich the AIC ``DESCRIPTION`` (which carries storeys/units in prose, not
    structured columns) when building precedent features.

    Args:
        text (str): Unstructured application or planning-report text.

    Returns:
        dict: Parsed fields (subset of ApplicationFeatures); ``{}`` on failure.

    Raises:
        ImportError: If the ``openai`` package is not installed.
    """
    messages = [
        {
            "role": "user",
            "content": (
                "Extract development application fields as STRICT JSON with keys height_m, "
                "total_units, affordable_units, retail_sqft, requested_variances (list). "
                "Use null for anything not stated. Text:\n" + text
            ),
        }
    ]
    return chat_json(messages)
