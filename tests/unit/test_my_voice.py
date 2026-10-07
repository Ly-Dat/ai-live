import json, threading, wave
from http.server import BaseHTTPRequestHandler, HTTPServer

from utils import my_voice, vieneu_tts


def make_wav(path, secs):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * secs))
    return str(path)


def serve(status=200):
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            seen["path"] = self.path
            seen["ctype"] = self.headers["Content-Type"]
            seen["body"] = self.rfile.read(n)
            self.send_response(status); self.end_headers(); self.wfile.write(b"{}")
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_refuses_without_consent_and_sends_nothing(tmp_path):
    clip = make_wav(tmp_path / "a.wav", 5)
    srv, seen = serve()
    ok, msg = my_voice.enroll_own_voice("Me", clip, False, {"api_url": f"http://127.0.0.1:{srv.server_port}"}, str(tmp_path / "c.json"))
    srv.shutdown()
    assert not ok and "own voice" in msg and not seen and my_voice.records(str(tmp_path / "c.json")) == []


def test_clip_length_checked(tmp_path):
    assert "3 to 8" in my_voice.check_clip(make_wav(tmp_path / "s.wav", 1))
    assert "trim" in my_voice.check_clip(make_wav(tmp_path / "l.wav", 30))
    assert my_voice.check_clip(make_wav(tmp_path / "ok.wav", 5)) == ""


def test_enroll_posts_multipart_and_records_consent(tmp_path):
    clip = make_wav(tmp_path / "a.wav", 5)
    srv, seen = serve()
    cp = str(tmp_path / "c.json")
    ok, _ = my_voice.enroll_own_voice("My Voice", clip, True, {"api_url": f"http://127.0.0.1:{srv.server_port}"}, cp)
    srv.shutdown()
    assert ok and seen["path"] == "/v1/voices" and seen["ctype"].startswith("multipart/form-data")
    assert b'name="name"' in seen["body"] and b"My Voice" in seen["body"] and b'name="file"' in seen["body"]
    rec = my_voice.records(cp)
    assert rec[0]["name"] == "My Voice" and rec[0]["statement"] == my_voice.STATEMENT


def test_server_down_and_bad_name(tmp_path):
    clip = make_wav(tmp_path / "a.wav", 5)
    ok, msg = my_voice.enroll_own_voice("Me", clip, True, {"api_url": "http://127.0.0.1:9"}, str(tmp_path / "c.json"))
    assert not ok and "not running" in msg and my_voice.records(str(tmp_path / "c.json")) == []
    assert not my_voice.enroll_own_voice("a/b", clip, True, {}, str(tmp_path / "c.json"))[0]
