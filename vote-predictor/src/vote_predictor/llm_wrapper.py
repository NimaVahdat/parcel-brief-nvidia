"""Qwen2.5-7B wrapper.

Two jobs:
1. Parse unstructured application text (e.g. a planning rationale paragraph) into
   the structured fields the XGBoost model expects.
2. Generate natural-language counterfactual explanations from the model's lever
   probabilities (e.g. "+12 affordable units → 11-0 approve, confidence 94%").
"""

import os


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")


def parse_application_text(text: str) -> dict:
    """Extract structured features from a free-text application description.

    TODO: call the local LLM via OpenAI-compatible API; use a strict JSON schema
    prompt; validate against schemas.ApplicationFeatures.
    """
    raise NotImplementedError("Wire up the local LLM endpoint.")


def write_counterfactual(prediction: dict, application: dict) -> list[dict]:
    """Turn raw lever deltas into natural-language recommendations.

    TODO: prompt the LLM with the application context, the lever list with deltas,
    and ask for short actionable rewrites grounded in the actual fields.
    """
    raise NotImplementedError("Wire up the local LLM endpoint.")
