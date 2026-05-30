"""Solo CLI for the opposition-generator pipeline.

Typical local flow:
    opposition-generator seed          # write the synthetic corpus to data/
    opposition-generator build-index   # embed it into the vector store (needs Ollama)
    opposition-generator demo          # full forecast for a sample project
"""

from __future__ import annotations

import json

import typer

from opposition_generator import config
from opposition_generator.schemas import ProjectDescription

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _sample_project() -> ProjectDescription:
    return ProjectDescription(
        height_m=42.0,
        total_units=84,
        affordable_units=0,
        use_mix={"residential": 0.85, "retail": 0.15},
        character_notes="brick mid-rise on Dundas Street West",
    )


@app.command()
def seed() -> None:
    """Write the committed synthetic corpus to data/deputations.jsonl."""
    from opposition_generator.index.corpus import CORPUS_PATH, load_seed

    config.ensure_data_dir()
    records = load_seed()
    with CORPUS_PATH.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    typer.echo(f"Wrote {len(records)} seed deputations to {CORPUS_PATH}")


@app.command("build-index")
def build_index_cmd() -> None:
    """Embed the corpus into the vector store (requires Ollama)."""
    from opposition_generator.index.embed import build_index

    n = build_index()
    backend = "pgvector" if config.DATABASE_URL else f"sqlite:{config.SQLITE_PATH}"
    typer.echo(f"Indexed {n} deputations into {backend}")


@app.command()
def retrieve(
    neighborhood: str = typer.Option("Trinity-Bellwoods", "--neighborhood", "-n"),
    query: str = typer.Option(
        "42m residential building, 84 units, no affordable", "--query", "-q"
    ),
    k: int = typer.Option(config.DEFAULT_TOP_K, "--k"),
    no_hyde: bool = typer.Option(False, "--no-hyde", help="skip HyDE query expansion"),
) -> None:
    """Run hybrid retrieval and print the top matches."""
    from opposition_generator.index.retrieve import retrieve as do_retrieve

    hits = do_retrieve(query, neighborhood, k, use_hyde=not no_hyde)
    if not hits:
        typer.echo("No matches (is the index built? run `build-index`).")
        raise typer.Exit(1)
    for i, h in enumerate(hits, 1):
        tag = "★" if h.same_neighborhood else " "
        typer.echo(
            f"{i:2d}. {tag} [{h.score:.4f}] {h.deputation.neighborhood} "
            f"({', '.join(h.deputation.concerns)})\n      {h.deputation.text[:120]}…"
        )


@app.command()
def demo(
    neighborhood: str = typer.Option("Trinity-Bellwoods", "--neighborhood", "-n"),
) -> None:
    """Full opposition forecast for a sample project (shows the degradation tier)."""
    from opposition_generator.generate import generate_with_meta

    result = generate_with_meta(_sample_project(), neighborhood=neighborhood)
    typer.echo(f"# mode={result.mode}  retrieved={result.retrieved_count}")
    typer.echo(json.dumps(result.forecast.model_dump(), indent=2))


@app.command()
def scrape(
    start_year: int = typer.Option(2022, "--start-year"),
    end_year: int = typer.Option(2026, "--end-year"),
    max_files: int = typer.Option(0, "--max-files", help="0 = no limit"),
    headful: bool = typer.Option(False, "--headful"),
) -> None:
    """Scrape deputation PDFs from TMMIS (requires the `scrape` extra)."""
    from opposition_generator.ingest import scrape_deputations

    paths = scrape_deputations(
        start_year=start_year,
        end_year=end_year,
        headless=not headful,
        max_files=max_files or None,
    )
    typer.echo(f"Downloaded {len(paths)} PDFs")


@app.command()
def ingest(limit: int = typer.Option(0, "--limit", help="0 = all")) -> None:
    """Extract + LLM-tag scraped PDFs into data/deputations.jsonl."""
    from opposition_generator.ingest import ingest_corpus

    n = ingest_corpus(limit=limit or None)
    typer.echo(f"Ingested {n} deputations to {config.DATA_DIR / 'deputations.jsonl'}")


if __name__ == "__main__":
    app()
