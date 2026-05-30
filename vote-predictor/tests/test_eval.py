"""End-to-end test: synthetic ingest -> profiles -> fallback eval beats naive baselines."""

import pytest
from vote_predictor import config, dataset, ingest
from vote_predictor.eval import evaluate


@pytest.fixture()
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect all data paths to a temp dir so the test is hermetic.

    Args:
        tmp_path: pytest temp directory fixture.
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        None. Patches ``config`` path constants in place.
    """
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(
        config, "APPLICATIONS_PARQUET", tmp_path / "processed" / "applications.parquet"
    )
    monkeypatch.setattr(config, "VOTES_PARQUET", tmp_path / "processed" / "votes.parquet")
    monkeypatch.setattr(config, "STAFF_RECS_PARQUET", tmp_path / "processed" / "staff_recs.parquet")
    monkeypatch.setattr(
        config, "TRAINING_TABLE_PARQUET", tmp_path / "processed" / "labeled_votes.parquet"
    )
    monkeypatch.setattr(
        config, "PROFILES_JSON", tmp_path / "processed" / "councillor_profiles.json"
    )


def test_fallback_agent_beats_baselines(temp_data_dir):
    """The grounded fallback arm should beat the naive baselines and clear chance on AUC."""
    ingest.generate_synthetic(n_applications=800, seed=11)
    report = evaluate(use_llm=False)

    assert report["meta"]["mode"] == "fallback"
    # Calibration: at least as sharp as councillor base-rate alone.
    assert report["fallback"]["brier"] <= report["base_rate"]["brier"] + 1e-6
    # Discrimination clears chance.
    assert report["fallback"]["auc"] >= 0.6
    # Committee outcomes on contested items beat a coin flip.
    assert report["fallback"]["outcome_accuracy_contested"] >= 0.6
    # The grounded arm beats the always-yes baseline on Brier.
    assert report["fallback"]["brier"] < report["always_yes"]["brier"]


def test_profiles_are_leakage_free(temp_data_dir):
    """Profiles built on the training subset do not absorb test-period outcomes."""
    import pandas as pd
    from vote_predictor import retrieval

    # A councillor votes Yes on a train item and No on a test item.
    votes = pd.DataFrame(
        [
            {"application_id": "train1", "councillor_id": "x", "committee": "te", "vote": "Yes"},
            {"application_id": "test1", "councillor_id": "x", "committee": "te", "vote": "No"},
        ]
    )
    train_only = votes[votes["application_id"] == "train1"]
    profiles = retrieval.build_councillor_profiles(votes=train_only, cache=False)
    # Profile sees only the train Yes vote, not the held-out No.
    assert profiles["x"]["yes_rate"] == 1.0
    assert profiles["x"]["n_votes"] == 1


def test_precedent_retrieval_respects_allowed_ids(temp_data_dir):
    """find_similar_applications only returns precedents in allowed_ids (no test-period leakage)."""
    from vote_predictor import retrieval

    ingest.generate_synthetic(n_applications=120, seed=4)
    application = {
        "parcel_id": "PARCEL-00001",
        "height_m": 42,
        "total_units": 120,
        "affordable_units": 18,
        "retail_sqft": 0,
        "requested_variances": [],
        "neighborhood": "x",
    }
    allowed = {"SYN-00002", "SYN-00003", "SYN-00004", "SYN-00005"}
    cases = retrieval.find_similar_applications(application, k=5, allowed_ids=allowed)
    assert cases, "expected at least one precedent"
    assert all(c["application_id"] in allowed for c in cases)


def test_eval_reports_abstain_rate(temp_data_dir):
    """The eval report surfaces the panel's abstain rate so mass-abstain is visible."""
    ingest.generate_synthetic(n_applications=300, seed=9)
    report = evaluate(use_llm=False)
    assert "abstain_rate" in report["panel"]
    assert "panel_abstain_rate" in report["meta"]


def test_eval_reports_verification_keys(temp_data_dir):
    """The report surfaces verification-layer rates and a verification_enabled meta flag."""
    ingest.generate_synthetic(n_applications=300, seed=9)
    report = evaluate(use_llm=False)
    assert "verifier_downgrade_rate" in report["panel"]
    assert "verifier_abstain_rate" in report["panel"]
    # In fallback mode the LLM Reasoner never runs, so the verification layer is inert.
    assert report["meta"]["verification_enabled"] is False
    assert report["meta"]["verifier_abstain_rate"] == 0.0


def test_eval_verify_ablation_adds_arm(temp_data_dir):
    """verify_ablation adds a panel_unverified arm; in fallback it matches the panel arm exactly."""
    ingest.generate_synthetic(n_applications=300, seed=9)
    report = evaluate(use_llm=False, verify_ablation=True)
    assert "panel_unverified" in report
    # Fallback panel never invokes verification, so verified and unverified arms are identical.
    assert report["panel"]["vote_accuracy"] == report["panel_unverified"]["vote_accuracy"]
    assert report["panel"]["brier"] == report["panel_unverified"]["brier"]


def test_base_rates_report_shape(temp_data_dir):
    """compute_base_rates returns the expected keys on a freshly built table."""
    ingest.generate_synthetic(n_applications=200, seed=3)
    table = dataset.build_training_table()
    rates = dataset.compute_base_rates(table)
    assert set(rates) == {"overall_yes_rate", "n_votes", "n_items", "contested_fraction"}
    assert rates["n_items"] == 200
