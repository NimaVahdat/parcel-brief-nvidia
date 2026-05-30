"""XGBoost training pipeline.

Joins applications ⋈ votes, builds features, fits a classifier, evaluates on a
held-out test set, persists the model to data/model.joblib.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def train() -> None:
    """Train the XGBoost vote predictor.

    TODO:
    1. Load data/applications.parquet and data/votes.parquet.
    2. Join on app_id; one row per (application, councillor).
    3. Build features via features.build_features.
    4. Stratified split, holding out the most recent 500 applications.
    5. Fit xgboost.XGBClassifier with reasonable defaults; tune later.
    6. Report accuracy + AUC + calibration on the held-out set.
    7. Persist with joblib.dump to data/model.joblib.
    """
    raise NotImplementedError(
        "Implement training pipeline. See README for the target feature set."
    )


if __name__ == "__main__":
    train()
