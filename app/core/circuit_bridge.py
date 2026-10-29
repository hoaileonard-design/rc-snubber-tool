"""Loopback-only bridge between CircuitJS and the existing waveform analyzer.

The browser receives only app-owned static files. Captures are append-only
illustration data, never a substitute for LTspice or hardware measurements.
"""

import csv
import hashlib
import io
import json
import math
import mimetypes
import queue
import secrets
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class CircuitBridge:
    MAX_BODY_BYTES = 4 * 1024 * 1024
    MAX_POINTS = 20_000
    MAX_CIRCUIT_BYTES = 256 * 1024
    MAX_METADATA_BYTES = 64 * 1024
    MAX_PENDING = 4
    SOURCE = "Falstad/CircuitJS illustration; not LTspice/hardware validation"
    STATIC_SUFFIXES = {".html", ".js", ".css", ".json", ".txt", ".svg", ".png", ".woff", ".woff2"}

    def __init__(self, web_root: Path, vendor_root: Path, capture_dir: Path,
                 initial_state: dict = None):
        self.web_root = Path(web_root).resolve()
        self.vendor_root = Path(vendor_root).resolve()
        self.capture_dir = Path(capture_dir).resolve()
        self._state = self._copy_object(initial_state or {})
        self._state_lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._captures = queue.Queue(maxsize=self.MAX_PENDING)
        self._server = self._thread = None
        self.url = self.origin = self.token = None

    @staticmethod
    def _copy_object(value):
        if not isinstance(value, dict):
            raise ValueError("Trạng thái/metadata phải là object JSON.")
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))

    def update_state(self, state: dict):
        state = self._copy_object(state)
        with self._state_lock:
            self._state.update(state)

    def pop_capture(self):
        try:
            return self._captures.get_nowait()
        except queue.Empty:
            return None

    def start(self) -> str:
        with self._lifecycle_lock:
            if self._server is not None:
                return self.url
            if not (self.web_root / "index.html").is_file():
                raise FileNotFoundError("Thiếu trang mạch tương tác index.html.")
            bridge = self

            class Handler(BaseHTTPRequestHandler):
                def setup(self):
                    super().setup()
                    self.connection.settimeout(5)

                def log_message(self, *_args):
                    # Session tokens and file names must not leak into HTTP logs.
                    pass

                def _respond(self, status, data, content_type="application/json; charset=utf-8"):
                    if isinstance(data, dict):
                        data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("X-Frame-Options", "SAMEORIGIN")
                    self.end_headers()
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                def _route(self, post=False):
                    expected_host = urlsplit(bridge.origin).netloc
                    hosts = self.headers.get_all("Host", [])
                    origins = self.headers.get_all("Origin", [])
                    if hosts != [expected_host] or len(origins) > 1:
                        self._respond(403, {"error": "Nguồn yêu cầu không hợp lệ."})
                        return None
                    if (post and origins != [bridge.origin]) or (origins and origins != [bridge.origin]):
                        self._respond(403, {"error": "Chỉ nhận yêu cầu từ trang mạch cục bộ."})
                        return None
                    try:
                        path = unquote(urlsplit(self.path).path, errors="strict")
                    except (ValueError, UnicodeError):
                        self._respond(400, {"error": "Đường dẫn không hợp lệ."})
                        return None
                    prefix = f"/{bridge.token}/"
                    if not path.startswith(prefix):
                        self._respond(404, {"error": "Không tìm thấy."})
                        return None
                    route = path[len(prefix):]
                    if "\\" in route or ":" in route or "\x00" in route or ".." in route.split("/"):
                        self._respond(404, {"error": "Không tìm thấy."})
                        return None
                    return route

                def do_GET(self):
                    route = self._route()
                    if route is None:
                        return
                    if route == "api/state":
                        with bridge._state_lock:
                            state = bridge._copy_object(bridge._state)
                        self._respond(200, state)
                        return
                    if route.startswith("api/"):
                        self._respond(404, {"error": "Không tìm thấy."})
                        return
                    if route.startswith("vendor/"):
                        root, relative = bridge.vendor_root, route[len("vendor/"):]
                    else:
                        root, relative = bridge.web_root, route or "index.html"
                    target = (root / relative).resolve()
                    if not target.is_relative_to(root) or target.suffix.lower() not in bridge.STATIC_SUFFIXES or not target.is_file():
                        self._respond(404, {"error": "Không tìm thấy."})
                        return
                    try:
                        data = target.read_bytes()
                    except OSError:
                        self._respond(404, {"error": "Không đọc được tài nguyên."})
                        return
                    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                    if target.suffix.lower() in {".html", ".js", ".css", ".json", ".txt", ".svg"}:
                        content_type += "; charset=utf-8"
                    self._respond(200, data, content_type)

                def do_POST(self):
                    route = self._route(post=True)
                    if route is None:
                        return
                    if route != "api/waveform":
                        self._respond(404, {"error": "Không tìm thấy."})
                        return
                    if self.headers.get("Transfer-Encoding"):
                        self._respond(400, {"error": "Yêu cầu cần Content-Length cố định."})
                        return
                    lengths = self.headers.get_all("Content-Length", [])
                    try:
                        if len(lengths) != 1:
                            raise ValueError
                        length = int(lengths[0])
                        if length <= 0:
                            raise ValueError
                    except ValueError:
                        self._respond(400, {"error": "Content-Length không hợp lệ."})
                        return
                    if length > bridge.MAX_BODY_BYTES:
                        self._respond(413, {"error": "Dữ liệu vượt giới hạn 4 MiB."})
                        return
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        self._respond(415, {"error": "Chỉ nhận application/json."})
                        return
                    try:
                        raw = self.rfile.read(length)
                        if len(raw) != length:
                            raise ValueError("Thiếu dữ liệu yêu cầu.")
                        payload = json.loads(raw.decode("utf-8"), parse_constant=bridge._invalid_constant)
                        capture = bridge._store_capture(payload)
                    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
                        self._respond(400, {"error": str(exc)[:240]})
                        return
                    except queue.Full:
                        self._respond(409, {"error": "App chưa nhận hết dạng sóng trước; thử lại sau."})
                        return
                    except OSError:
                        self._respond(500, {"error": "Không lưu được dạng sóng; kiểm tra thư mục ghi của app."})
                        return
                    self._respond(201, {"filename": capture["filename"], "sha256": capture["sha256"],
                                        "n_points": capture["metadata"]["n_points"]})

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.daemon_threads = True
            server.block_on_close = False
            self.token = secrets.token_urlsafe(24)
            self.origin = f"http://127.0.0.1:{server.server_port}"
            self.url = f"{self.origin}/{self.token}/"
            self._server = server
            self._thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05},
                                            name="CircuitJS-loopback", daemon=True)
            self._thread.start()
            return self.url

    @staticmethod
    def _invalid_constant(_value):
        raise ValueError("Dữ liệu JSON chứa NaN hoặc vô cực.")

    def _store_capture(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Dữ liệu phải là object JSON.")
        times, voltages = payload.get("times"), payload.get("voltages")
        if not isinstance(times, list) or not isinstance(voltages, list):
            raise ValueError("Cần danh sách times và voltages.")
        if len(times) != len(voltages) or not 10 <= len(times) <= self.MAX_POINTS:
            raise ValueError("Cần 10–20.000 cặp thời gian/điện áp.")
        if not all(type(value) in (int, float) and math.isfinite(value) for value in (*times, *voltages)):
            raise ValueError("Thời gian và điện áp phải là số hữu hạn.")
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Thời gian phải tăng liên tục, không trùng điểm.")
        circuit_text = payload.get("circuit_text", "")
        if not isinstance(circuit_text, str) or len(circuit_text.encode("utf-8")) > self.MAX_CIRCUIT_BYTES:
            raise ValueError("Sơ đồ phải là văn bản, tối đa 256 KiB.")
        metadata = self._copy_object(payload.get("metadata", {}))
        if len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) > self.MAX_METADATA_BYTES:
            raise ValueError("Metadata vượt giới hạn 64 KiB.")
        csv_text = io.StringIO(newline="")
        writer = csv.writer(csv_text)
        writer.writerow(["Time", "Voltage"])
        writer.writerows(zip(times, voltages))
        csv_bytes = csv_text.getvalue().encode("utf-8")
        now = datetime.now(UTC)
        digest = hashlib.sha256(csv_bytes).hexdigest()
        metadata.update(source=self.SOURCE, captured_at_utc=now.isoformat(), n_points=len(times),
                        time_unit="s", voltage_unit="V", circuit_text=circuit_text,
                        circuit_sha256=hashlib.sha256(circuit_text.encode("utf-8")).hexdigest(),
                        waveform_sha256=digest)
        filename = f"falstad_{now.strftime('%Y%m%dT%H%M%S%fZ')}_{secrets.token_hex(8)}.csv"
        with self._capture_lock:
            if self._captures.full():
                raise queue.Full
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            csv_path = self.capture_dir / filename
            json_path = csv_path.with_suffix(".json")
            csv_owned = json_owned = False
            try:
                with csv_path.open("xb") as output:
                    csv_owned = True
                    output.write(csv_bytes)
                with json_path.open("x", encoding="utf-8") as output:
                    json_owned = True
                    json.dump(metadata, output, ensure_ascii=False, allow_nan=False, indent=2)
            except OSError:
                # Only these newly owned names are eligible for cleanup.
                if csv_owned:
                    csv_path.unlink(missing_ok=True)
                if json_owned:
                    json_path.unlink(missing_ok=True)
                raise
            capture = dict(path=str(csv_path), metadata_path=str(json_path), filename=filename,
                           sha256=digest, metadata=metadata)
            self._captures.put_nowait(capture)
        return capture

    def stop(self):
        with self._lifecycle_lock:
            if self._server is None:
                return
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=2)
            self._server = self._thread = None
