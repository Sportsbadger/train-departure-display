from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from config import loadConfig  # noqa: E402


def test_adsb_config_defaults_to_disabled_train_only(monkeypatch):
    for key in [
        "adsbEnabled",
        "transportModes",
        "modeSwitchInterval",
        "adsbHomeLat",
        "adsbHomeLon",
        "adsbUserAgent",
        "adsbRouteLookupEnabled",
        "adsbRouteApiUrl",
        "adsbRouteFetchTimeout",
        "adsbRouteDisplay",
        "planeAlertEnabled",
        "planeAlertSourceUrl",
        "planeAlertFetchTimeout",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = loadConfig()

    assert config["adsb"]["enabled"] is False
    assert config["transport"]["modes"] == "train"
    assert config["transport"]["modeSwitchInterval"] == 300
    assert config["adsb"]["homeLat"] is None
    assert config["adsb"]["homeLon"] is None
    assert config["adsb"]["userAgent"].startswith("Mozilla/5.0")
    assert config["adsb"]["routeLookupEnabled"] is False
    assert "routeset" in config["adsb"]["routeApiUrl"]
    assert config["adsb"]["routeFetchTimeout"] == 4.0
    assert config["adsb"]["routeDisplay"] == "iata"
    assert config["planeAlert"]["enabled"] is False
    assert "planefence/pa_query.php" in config["planeAlert"]["sourceUrl"]
    assert config["planeAlert"]["fetchTimeout"] == 15.0


def test_adsb_config_parses_enabled_values(monkeypatch):
    monkeypatch.setenv("adsbEnabled", "True")
    monkeypatch.setenv("transportModes", "train,adsb")
    monkeypatch.setenv("modeSwitchInterval", "60")
    monkeypatch.setenv("adsbHomeLat", "51.5")
    monkeypatch.setenv("adsbHomeLon", "-0.1")
    monkeypatch.setenv("adsbFetchTimeout", "0")
    monkeypatch.setenv("adsbUserAgent", "CustomAgent/1.0")
    monkeypatch.setenv("adsbDisplayCount", "0")
    monkeypatch.setenv("adsbRouteLookupEnabled", "True")
    monkeypatch.setenv("adsbRouteApiUrl", "https://api.example.test/routeset")
    monkeypatch.setenv("adsbRouteFetchTimeout", "0")
    monkeypatch.setenv("adsbRouteDisplay", "city")
    monkeypatch.setenv("planeAlertEnabled", "True")
    monkeypatch.setenv("planeAlertFetchTimeout", "0")
    monkeypatch.setenv("planeAlertDisplayCount", "0")
    monkeypatch.setenv("planeAlertMaxAgeHours", "12")

    config = loadConfig()

    assert config["adsb"]["enabled"] is True
    assert config["transport"]["modes"] == "train,adsb"
    assert config["transport"]["modeSwitchInterval"] == 60
    assert config["adsb"]["homeLat"] == 51.5
    assert config["adsb"]["homeLon"] == -0.1
    assert config["adsb"]["fetchTimeout"] == 0.1
    assert config["adsb"]["userAgent"] == "CustomAgent/1.0"
    assert config["adsb"]["displayCount"] == 1
    assert config["adsb"]["routeLookupEnabled"] is True
    assert config["adsb"]["routeApiUrl"] == "https://api.example.test/routeset"
    assert config["adsb"]["routeFetchTimeout"] == 0.1
    assert config["adsb"]["routeDisplay"] == "city"
    assert config["planeAlert"]["enabled"] is True
    assert config["planeAlert"]["fetchTimeout"] == 0.1
    assert config["planeAlert"]["displayCount"] == 1
    assert config["planeAlert"]["maxAgeHours"] == 12.0
