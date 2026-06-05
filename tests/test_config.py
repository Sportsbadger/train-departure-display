from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from config import loadConfig, parse_float_env, parse_int_env  # noqa: E402


def test_parse_int_env_enforces_minimum(monkeypatch) -> None:
    monkeypatch.setenv("exampleInt", "0")

    assert parse_int_env("exampleInt", 5, minimum=1) == 1


def test_parse_float_env_handles_empty_and_minimum(monkeypatch) -> None:
    monkeypatch.setenv("exampleFloat", "")
    assert parse_float_env("exampleFloat", 1.5, minimum=1.0) == 1.5

    monkeypatch.setenv("exampleFloat", "0.05")
    assert parse_float_env("exampleFloat", 1.5, minimum=0.1) == 0.1


def test_load_config_includes_adsb_defaults(monkeypatch) -> None:
    for key in (
        "adsbJsonUrl",
        "adsbHost",
        "adsbReceiverLat",
        "adsbReceiverLon",
        "adsbMaxDistanceNm",
        "adsbMinAltitude",
        "adsbMaxAltitude",
    ):
        monkeypatch.delenv(key, raising=False)

    config = loadConfig()

    assert config["adsb"]["sourceType"] == "readsb-json"
    assert config["adsb"]["jsonUrl"] == ""
    assert config["adsb"]["refreshTime"] == 5
    assert config["adsb"]["receiverLat"] is None
    assert config["adsb"]["minAltitude"] is None
