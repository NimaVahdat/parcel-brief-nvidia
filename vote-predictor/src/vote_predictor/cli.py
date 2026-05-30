"""Solo demo CLI."""

import json

import typer

from vote_predictor.infer import predict
from vote_predictor.schemas import ApplicationFeatures

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def demo() -> None:
    """Run a mock prediction and print the result."""
    application = ApplicationFeatures(
        parcel_id="543-dundas-w",
        height_m=42.0,
        total_units=84,
        affordable_units=0,
        retail_sqft=2400,
        use_mix={"residential": 0.85, "retail": 0.15},
        neighborhood="Trinity-Bellwoods",
    )
    councillors = ["bravo", "malik", "chan", "okonkwo", "smith"]
    result = predict(application, councillors)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    app()
