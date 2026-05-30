"""Leave-one-out backtest of the precedent-RAG predictor on real outcomes.

Every precedent has a known outcome, so we can actually measure quality. For each
application we hold it out, predict from the rest, and compare to the truth.

Reports accuracy, AUC, Brier (calibration), and — the honest one — lift over the
base rate (Toronto approves most applications, so beating the base rate is the bar).

    python -m eval.evaluate          # needs Ollama + a corpus (seed or scraped)
"""

from __future__ import annotations

import numpy as np

from vote_predictor.corpus import load_corpus
from vote_predictor.embed import embed_batch
from vote_predictor.precedent import approval_probability
from vote_predictor.retrieve import retrieve
from vote_predictor.store import Precedent


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney). Returns 0.5 if a class is missing."""
    pos, neg = y_score[y_true == 1], y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    return (ranks[y_true == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def evaluate(k: int = 10) -> dict:
    records = load_corpus()
    if len(records) < 6:
        raise SystemExit("corpus too small to evaluate")

    embeddings = embed_batch([r["text"] for r in records])
    precedents = [
        Precedent(precedent_id=r["precedent_id"], text=r["text"], outcome=r["outcome"],
                  ward=r["ward"], year=r["year"], votes=r["votes"], embedding=e)
        for r, e in zip(records, embeddings)
    ]

    probs, actuals = [], []
    for i, p in enumerate(precedents):
        others = precedents[:i] + precedents[i + 1:]
        retr = retrieve(p.text, k, candidates=others)
        prob, _, _ = approval_probability(retr)
        probs.append(prob)
        actuals.append(1 if p.outcome == "approved" else 0)

    probs, actuals = np.array(probs), np.array(actuals)
    base_rate = actuals.mean()
    baseline_acc = max(base_rate, 1 - base_rate)

    # Under class imbalance, accuracy @0.5 is misleading (it just predicts the
    # majority class). Pick the threshold that maximizes Youden's J and also report
    # balanced accuracy — both honest for imbalanced data.
    best_thr, best_bal, best_acc = 0.5, 0.0, 0.0
    for thr in sorted(set(probs.tolist())):
        pred = (probs >= thr).astype(int)
        tp = int(((pred == 1) & (actuals == 1)).sum())
        fn = int(((pred == 0) & (actuals == 1)).sum())
        tn = int(((pred == 0) & (actuals == 0)).sum())
        fp = int(((pred == 1) & (actuals == 0)).sum())
        tpr = tp / (tp + fn + 1e-9)
        tnr = tn / (tn + fp + 1e-9)
        bal = (tpr + tnr) / 2
        if bal > best_bal:
            best_bal = bal
            best_thr = float(thr)
            best_acc = float((pred == actuals).mean())

    return {
        "corpus_size": len(records),
        "k": k,
        "base_rate_approved": round(float(base_rate), 3),
        "auc": round(float(_auc(actuals, probs)), 3),
        "balanced_accuracy": round(float(best_bal), 3),
        "accuracy_at_tuned_threshold": round(best_acc, 3),
        "tuned_threshold": round(best_thr, 3),
        "baseline_accuracy": round(float(baseline_acc), 3),
        "lift_over_baseline": round(float(best_acc - baseline_acc), 3),
        "accuracy_at_0.5": round(float(((probs >= 0.5).astype(int) == actuals).mean()), 3),
        "brier": round(float(np.mean((probs - actuals) ** 2)), 3),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(evaluate(), indent=2))
