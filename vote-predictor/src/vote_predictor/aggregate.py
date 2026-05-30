"""Deterministic probability math for combining per-councillor predictions.

Pure functions, no ML: given per-councillor Yes-probabilities (from the LLM agent or the
fallback), turn them into a committee-level approval probability and identify swings.
"""

from __future__ import annotations

import math

from vote_predictor import config


def sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid.

    Args:
        x (float): Real-valued logit.

    Returns:
        float: ``1 / (1 + e^-x)`` in (0, 1).
    """
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def sigmoid_inverse(p: float) -> float:
    """Logit (inverse sigmoid) of a probability, clamped away from 0 and 1.

    Args:
        p (float): A probability in (0, 1).

    Returns:
        float: The corresponding logit.
    """
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def poisson_binomial_majority(probs: list[float]) -> float:
    """Probability that a strict majority of independent yes/no votes are Yes.

    Uses the exact Poisson-binomial distribution (DP over the per-voter probabilities)
    rather than a naive mean, so a committee of confident-but-split members aggregates
    correctly.

    Args:
        probs (list[float]): Per-councillor probabilities of voting Yes.

    Returns:
        float: Probability the Yes count exceeds half the committee. 0.0 if empty.
    """
    n = len(probs)
    if n == 0:
        return 0.0
    dist = [1.0] + [0.0] * n  # dist[k] = P(exactly k Yes votes)
    for p in probs:
        for k in range(n, 0, -1):
            dist[k] = dist[k] * (1 - p) + dist[k - 1] * p
        dist[0] *= 1 - p
    needed = n // 2 + 1
    return float(sum(dist[needed:]))


def swing_councillors(per_councillor: dict[str, float]) -> list[str]:
    """Identify councillors whose vote is close to a coin flip.

    Args:
        per_councillor (dict[str, float]): Map of councillor id -> Yes-probability.

    Returns:
        list[str]: Councillor ids within ``config.SWING_BAND`` of 0.5, most uncertain first.
    """
    return sorted(
        (c for c, p in per_councillor.items() if abs(p - 0.5) <= config.SWING_BAND),
        key=lambda c: abs(per_councillor[c] - 0.5),
    )
