"""Solo CLI for vote-predictor: ingest, build profiles, eval, coverage, and a demo prediction."""

import json
import logging

import typer

from vote_predictor.infer import predict_with_trace
from vote_predictor.schemas import ApplicationFeatures

# CLI surfaces the modules' INFO logs (e.g. the eval report, ingest warnings) as plain lines.
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="vote-predictor CLI")


@app.command()
def ingest(
    synthetic: bool = typer.Option(
        False, help="Use the offline synthetic dataset instead of the real sources."
    ),
    seed_items: str = typer.Option(
        "", help="Comma-separated agenda item ids to seed votes from the non-Akamai mirror."
    ),
    terms: str = typer.Option(
        "", help="Comma-separated council term ids for the official vote CSV."
    ),
    max_pages: int = typer.Option(0, help="Cap CKAN pages pulled (0 = full corpus)."),
) -> None:
    """Land source data to parquet (real sources by default; --synthetic for offline/CI).

    Args:
        synthetic (bool): When True, generate the offline synthetic dataset.
        seed_items (str): Agenda item ids (comma-separated) to seed votes from the mirror.
        terms (str): Council term ids (comma-separated) for the official vote CSV (Playwright).
        max_pages (int): Cap CKAN pages pulled (0 = all).

    Returns:
        None.
    """
    from vote_predictor.ingest import ingest as run_ingest

    report = run_ingest(
        synthetic=synthetic,
        terms=[t for t in terms.split(",") if t] or None,
        seed_item_ids=[s for s in seed_items.split(",") if s] or None,
        max_pages=max_pages or None,
    )
    if report:
        typer.echo(json.dumps(report, indent=2))
    typer.echo("ingest complete.")


@app.command("build-profiles")
def build_profiles() -> None:
    """Build and cache per-councillor voting profiles from the ingested votes.

    Returns:
        None.
    """
    from vote_predictor.retrieval import build_councillor_profiles

    profiles = build_councillor_profiles()
    typer.echo(f"built {len(profiles)} councillor profiles.")


@app.command()
def coverage() -> None:
    """Report how much of the application corpus links to a recorded vote (real ingest).

    Returns:
        None.
    """
    import pandas as pd

    from vote_predictor import config, crosswalk

    if not config.CROSSWALK_PARQUET.exists():
        typer.echo("No crosswalk found. Run a real `ingest` first.")
        raise typer.Exit(1)
    apps = pd.read_parquet(config.APPLICATIONS_PARQUET)
    xwalk = pd.read_parquet(config.CROSSWALK_PARQUET)
    typer.echo(json.dumps(crosswalk.coverage_report(apps, xwalk), indent=2))


@app.command()
def evaluate(
    use_llm: bool = typer.Option(False, help="Score the LLM panel instead of the fallback."),
    ablations: bool = typer.Option(False, help="Also run the no-grounding LLM ablation arm."),
    limit: int = typer.Option(0, help="Cap test applications (0 = all)."),
) -> None:
    """Backtest the panel on a held-out time split against baselines and ablations.

    Args:
        use_llm (bool): When True, evaluate the LLM panel (needs a running endpoint).
        ablations (bool): When True, also run the no-grounding ablation arm.
        limit (int): Optional cap on the number of test applications.

    Returns:
        None.
    """
    from vote_predictor.eval import evaluate as run_eval

    run_eval(use_llm=use_llm, limit=limit or None, ablations=ablations)


@app.command()
def demo() -> None:
    """Print a real prediction plus its per-councillor reasoning trace.

    Returns:
        None.
    """
    application = ApplicationFeatures(
        parcel_id="DEMO-PARCEL-001",
        height_m=42.0,
        total_units=120,
        affordable_units=18,
        retail_sqft=4200.0,
        use_mix={"residential": 0.85, "retail": 0.15},
        neighborhood="Trinity-Bellwoods",
        requested_variances=["height", "density", "rear-setback"],
    )
    # Use the synthetic committee ids so `ingest --synthetic` + demo shows grounded reasoning
    # (arbitrary names would have no record and the Skeptic would abstain them to the prior).
    councillors = ["toronto0", "toronto1", "toronto2", "toronto3", "toronto4"]
    prediction, trace = predict_with_trace(application, councillors)
    typer.echo(
        json.dumps(
            {"prediction": prediction.model_dump(), "agent_trace": trace.model_dump()}, indent=2
        )
    )


if __name__ == "__main__":
    app()
