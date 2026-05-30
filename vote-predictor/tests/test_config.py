from pathlib import Path

from vote_predictor import config


def test_default_data_dir_is_component_local() -> None:
    expected = Path(__file__).resolve().parents[1] / "data"
    assert config.DATA_DIR == expected.resolve()
