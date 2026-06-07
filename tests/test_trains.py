from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from trains import escapeXml, loadDeparturesForStation  # noqa: E402


def test_escape_xml_escapes_request_values():
    assert escapeXml("A&B<'\">") == "A&amp;B&lt;&apos;&quot;&gt;"


def test_load_departures_queries_multiple_destinations(monkeypatch):
    posted_payloads = []

    class FakeResponse:
        text = "<xml />"

    def fake_post(_url, data, headers, timeout):
        posted_payloads.append((data, timeout))
        return FakeResponse()

    responses = iter(
        [
            (
                [
                    {
                        "aimed_departure_time": "10:00",
                        "destination_name": "Oxford",
                    }
                ],
                "London Paddington",
            ),
            (
                [
                    {
                        "aimed_departure_time": "09:00",
                        "destination_name": "Reading",
                    },
                    {
                        "aimed_departure_time": "10:00",
                        "destination_name": "Oxford",
                    },
                ],
                "London Paddington",
            ),
        ]
    )

    monkeypatch.setattr("trains.requests.post", fake_post)
    monkeypatch.setattr("trains.ProcessDepartures", lambda *_: next(responses))

    departures, station_name = loadDeparturesForStation(
        {
            "departureStation": "PAD",
            "destinationStation": ["OXF", "RDG"],
            "timeOffset": "0",
        },
        "api-key",
        "10",
    )

    assert station_name == "London Paddington"
    assert [departure["destination_name"] for departure in departures] == [
        "Reading",
        "Oxford",
    ]
    assert len(posted_payloads) == 2
    assert all(timeout == 10 for _data, timeout in posted_payloads)
    assert "<ldb:filterCrs>OXF</ldb:filterCrs>" in posted_payloads[0][0]
    assert "<ldb:filterCrs>RDG</ldb:filterCrs>" in posted_payloads[1][0]
