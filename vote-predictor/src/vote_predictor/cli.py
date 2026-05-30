"""Solo CLI for the precedent-RAG vote predictor.

Typical local flow:
    vote-predictor seed          # write the synthetic precedent corpus
    vote-predictor build-index   # embed it (needs Ollama)
    vote-predictor demo          # predict for a sample application
"""

from __future__ import annotations

import json

import typer

from vote_predictor import config
from vote_predictor.schemas import ApplicationFeatures

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _sample_application() -> ApplicationFeatures:
    return ApplicationFeatures(
        parcel_id="543-dundas-w",
        height_m=42.0,
        total_units=84,
        affordable_units=0,
        retail_sqft=2400,
        use_mix={"residential": 0.85, "retail": 0.15},
        neighborhood="Trinity-Bellwoods",
    )


@app.command()
def seed() -> None:
    """Write the committed synthetic precedent corpus to data/precedents.jsonl."""
    from vote_predictor.corpus import CORPUS_PATH, load_seed

    config.ensure_data_dir()
    rows = load_seed()
    with CORPUS_PATH.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    typer.echo(f"Wrote {len(rows)} seed precedents to {CORPUS_PATH}")


@app.command("build-index")
def build_index_cmd() -> None:
    """Embed the precedent corpus into the vector store (needs Ollama)."""
    from vote_predictor.embed import build_index

    n = build_index()
    backend = "pgvector" if config.DATABASE_URL else f"sqlite:{config.SQLITE_PATH}"
    typer.echo(f"Indexed {n} precedents into {backend}")


@app.command()
def demo(councillors: str = typer.Option("bravo,malik,chan,okonkwo,smith", "--councillors")) -> None:
    """Predict the council outcome for a sample application (shows the tier)."""
    from vote_predictor.infer import predict_with_meta

    result = predict_with_meta(_sample_application(), councillors.split(","))
    typer.echo(f"# mode={result.mode}  retrieved={result.retrieved} "
               f"approved_of_retrieved={result.approved_of_retrieved}")
    typer.echo(json.dumps(result.prediction.model_dump(), indent=2))


@app.command()
def fetch(
    ratio: int = typer.Option(3, "--ratio", help="approved-per-refused balance"),
) -> None:
    """Build the precedent corpus from Toronto's Development Applications open data."""
    from vote_predictor.ingest import build_corpus

    n = build_corpus(approved_per_refused=ratio)
    typer.echo(f"Wrote {n} precedents. Next: `vote-predictor build-index`")


if __name__ == "__main__":
    app()
