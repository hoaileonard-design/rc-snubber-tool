import hashlib
import http.client
import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app.core.circuit_bridge import CircuitBridge
from app.core import circuit_bridge
from app.core.waveform_analyzer import WaveformAnalyzer


@pytest.fixture
def bridge(tmp_path):
    web, vendor, captures = (tmp_path / name for name in ("web", "vendor", "captures"))
    web.mkdir()
    vendor.mkdir()
    (web / "index.html").write_text("<h1>App bridge</h1>", encoding="utf-8")
    (web / "application.py").write_text("not served", encoding="utf-8")
    (vendor / "sim.js").write_text("window.example = true;", encoding="utf-8")
    instance = CircuitBridge(web, vendor, captures, {"R_ohm": 10, "C_F": 4.7e-9})
    instance.start()
    yield instance
    instance.stop()


def request(bridge, method="GET", route="", payload=None, headers=None, body=None):
    parsed = urlsplit(bridge.url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    actual_headers = {"Origin": bridge.origin} if method == "POST" else {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        actual_headers["Content-Type"] = "application/json"
    if headers:
        actual_headers.update(headers)
    connection.request(method, parsed.path + route, body=body, headers=actual_headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def waveform():
    return dict(times=[i * 1e-9 for i in range(20)], voltages=[24 + i / 10 for i in range(20)],
                circuit_text="$ sample circuit\nr 0 0 10 0 0 10", metadata={"kind": "RC", "node": "A-B"})


def test_static_state_and_update(bridge):
    status, headers, body = request(bridge)
    assert status == 200 and b"App bridge" in body
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert request(bridge, route="vendor/sim.js")[0] == 200
    assert request(bridge, route="application.py")[0] == 404
    assert request(bridge, route="vendor/")[0] == 404
    bridge.update_state({"R_ohm": 22})
    status, _, body = request(bridge, route="api/state")
    assert status == 200 and json.loads(body) == {"R_ohm": 22, "C_F": 4.7e-9}


def test_capture_saved_append_only_and_usable_by_existing_analyzer(bridge):
    original = waveform()
    original["metadata"]["source"] = "claimed hardware"
    status, _, body = request(bridge, "POST", "api/waveform", original)
    assert status == 201 and json.loads(body)["n_points"] == 20
    capture = bridge.pop_capture()
    assert capture and bridge.pop_capture() is None
    csv_path = Path(capture["path"])
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == capture["sha256"]
    metadata = json.loads(Path(capture["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["source"] == CircuitBridge.SOURCE
    assert metadata["circuit_text"] == original["circuit_text"]
    t, v = WaveformAnalyzer.load_file(str(csv_path))
    assert len(t) == 20 and v[-1] == pytest.approx(original["voltages"][-1])
    assert request(bridge, "POST", "api/waveform", original)[0] == 201
    assert bridge.pop_capture()["path"] != capture["path"]
    assert len(list(bridge.capture_dir.glob("*.csv"))) == 2


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(times=[0] * 20),
    lambda x: x.update(times=[1] * 9, voltages=[24] * 9),
    lambda x: x.update(voltages=[24] * 19),
    lambda x: x["times"].__setitem__(5, float("nan")),
    lambda x: x["voltages"].__setitem__(5, float("inf")),
    lambda x: x["times"].__setitem__(5, True),
    lambda x: x.update(metadata=[]),
    lambda x: x.update(circuit_text="x" * (CircuitBridge.MAX_CIRCUIT_BYTES + 1)),
    lambda x: x.update(metadata={"text": "x" * CircuitBridge.MAX_METADATA_BYTES}),
])
def test_bad_capture_never_creates_files(bridge, mutate):
    payload = waveform()
    mutate(payload)
    assert request(bridge, "POST", "api/waveform", payload)[0] == 400
    assert bridge.pop_capture() is None
    assert not bridge.capture_dir.exists()


def test_invalid_json_and_body_limits(bridge):
    assert request(bridge, "POST", "api/waveform", body=b"{", headers={"Content-Type": "application/json"})[0] == 400
    assert request(bridge, "POST", "api/waveform", body=b"{}", headers={"Content-Type": "text/plain"})[0] == 415
    assert request(bridge, "POST", "api/waveform", body=b"{}", headers={"Content-Type": "application/json",
                   "Content-Length": str(CircuitBridge.MAX_BODY_BYTES + 1)})[0] == 413


def test_capture_count_bound_and_collision_preserve_existing_file(bridge, monkeypatch):
    payload = waveform()
    payload.update(times=list(range(bridge.MAX_POINTS + 1)), voltages=[24] * (bridge.MAX_POINTS + 1))
    assert request(bridge, "POST", "api/waveform", payload)[0] == 400

    class FixedClock:
        @staticmethod
        def now(_zone):
            return datetime(2026, 10, 29, tzinfo=UTC)

    monkeypatch.setattr(circuit_bridge, "datetime", FixedClock)
    monkeypatch.setattr(circuit_bridge.secrets, "token_hex", lambda _length: "fixedcollision")
    assert request(bridge, "POST", "api/waveform", waveform())[0] == 201
    capture = bridge.pop_capture()
    original = Path(capture["path"]).read_bytes()
    assert request(bridge, "POST", "api/waveform", waveform())[0] == 500
    assert Path(capture["path"]).read_bytes() == original
    assert Path(capture["metadata_path"]).is_file()


@pytest.mark.parametrize("route", ["../secret.txt", "%2e%2e/secret.txt", "vendor/%2e%2e/secret.txt",
                                  "vendor/%5c..%5csecret.txt", "vendor/C:%5csecret.txt"])
def test_no_path_traversal(bridge, route):
    assert request(bridge, route=route)[0] == 404


def test_foreign_host_origin_and_missing_token_rejected(bridge):
    assert request(bridge, headers={"Host": "evil.example"})[0] == 403
    assert request(bridge, headers={"Origin": "https://evil.example"})[0] == 403
    assert request(bridge, "POST", "api/waveform", waveform(), headers={"Origin": "null"})[0] == 403
    parsed = urlsplit(bridge.url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    connection.request("POST", parsed.path + "api/waveform", body=b"{}", headers={"Content-Type": "application/json"})
    assert connection.getresponse().status == 403
    connection.close()
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    connection.request("GET", "/api/state")
    assert connection.getresponse().status == 404
    connection.close()


def test_queue_bounded_and_lifecycle(bridge):
    original_url = bridge.url
    assert bridge.start() == original_url
    for _ in range(bridge.MAX_PENDING):
        assert request(bridge, "POST", "api/waveform", waveform())[0] == 201
    assert request(bridge, "POST", "api/waveform", waveform())[0] == 409
    assert len(list(bridge.capture_dir.glob("*.csv"))) == bridge.MAX_PENDING
    bridge.pop_capture()
    assert request(bridge, "POST", "api/waveform", waveform())[0] == 201
    port = urlsplit(original_url).port
    bridge.stop()
    bridge.stop()
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=.3)
    assert bridge.start() != original_url
