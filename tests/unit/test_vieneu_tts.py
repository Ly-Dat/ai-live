import json, os, sys, threading, wave
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils import vieneu_tts  # noqa: E402


class Stub(BaseHTTPRequestHandler):
    seen = {}

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Stub.seen = body
        pcm = b"\x01\x00" * 4800
        self.send_response(200)
        self.send_header("X-Sample-Rate", str(body.get("sample_rate", 48000)))
        self.end_headers()
        self.wfile.write(pcm)

    def do_GET(self):
        data = {"/v1/voices": {"object": "list", "data": [{"id": "Mai Anh"}, {"name": "Hải Đăng"}, "Phạm Tuyên"]},
                "/health": {"status": "ok"}}.get(self.path, {})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def serve():
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_synthesize_writes_valid_wav(tmp_path):
    srv, url = serve()
    out = vieneu_tts.synthesize("Xin chào", {"api_url": url, "voice": "Mai Anh", "sample_rate": 24000}, str(tmp_path / "a.wav"))
    srv.shutdown()
    assert out and Stub.seen["voice"] == "Mai Anh" and Stub.seen["response_format"] == "pcm"
    with wave.open(out) as w:
        assert w.getframerate() == 24000 and w.getnchannels() == 1 and w.getnframes() == 4800


def test_voices_and_health():
    srv, url = serve()
    assert vieneu_tts.list_voices(url) == ["Mai Anh", "Hải Đăng", "Phạm Tuyên"]
    assert vieneu_tts.is_up(url)
    srv.shutdown()


def test_unreachable_returns_none(tmp_path):
    cfg = {"api_url": "http://127.0.0.1:1", "timeout": 1}
    assert vieneu_tts.synthesize("hi", cfg, str(tmp_path / "x.wav")) is None
    assert vieneu_tts.list_voices("http://127.0.0.1:1") == []
    assert not vieneu_tts.is_up("http://127.0.0.1:1")
    assert vieneu_tts.synthesize("   ", cfg, str(tmp_path / "y.wav")) is None
