"""ComfyUI engine for the avatar studio: offline, with a scripted fake server."""
import json

from utils import avatar_gen as g

PNG = b"\x89PNG-fake"


class Fake:
    def __init__(self, ckpts=("sd15.safetensors", "animagine-xl-3.1.safetensors"), ready_after=2, down=False):
        self.calls, self.polls, self.ready_after, self.ckpts, self.down = [], 0, ready_after, list(ckpts), down

    def __call__(self, url, body, timeout):
        self.calls.append((url, body))
        if self.down:
            raise OSError("refused")
        if url.endswith("/system_stats"):
            return b"{}"
        if "object_info" in url:
            return json.dumps({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [self.ckpts]}}}}).encode()
        if url.endswith("/prompt"):
            return b'{"prompt_id":"p1"}'
        if "/history/" in url:
            self.polls += 1
            if self.polls < self.ready_after:
                return b"{}"
            return json.dumps({"p1": {"outputs": {"7": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}}}).encode()
        if "/view" in url:
            return PNG
        raise AssertionError(url)


CFG = {**g.DEFAULTS, "engine": "comfy", "timeout": 10}


def test_default_port_is_comfys(monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    f = Fake()
    assert g.check_server(CFG, f) == ""
    assert f.calls[0][0] == "http://127.0.0.1:8188/system_stats"
    assert g.check_server({**CFG, "port": 9000}, f) == "" and f.calls[-1][0].startswith("http://127.0.0.1:9000")


def test_offline_gives_setup_guidance(tmp_path):
    msg = g.check_server(CFG, Fake(down=True))
    assert "ComfyUI" in msg and "checkpoints" in msg and "without it" in msg
    assert g.generate_pack({"name": "x"}, CFG, str(tmp_path / "o"), fetch=Fake(down=True)) == {"made": [], "failed": {"all": msg}}


def test_txt2img_prefers_animagine_and_returns_png(monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    f = Fake()
    assert g.txt2img(CFG, "1girl", 7, f) == PNG
    graph = next(b for u, b in f.calls if u.endswith("/prompt"))["prompt"]
    assert graph["1"]["inputs"]["ckpt_name"] == "animagine-xl-3.1.safetensors"
    assert graph["2"]["inputs"]["text"] == "1girl" and graph["5"]["inputs"]["seed"] == 7 and graph["4"]["class_type"] == "EmptyLatentImage"


def test_img2img_starts_from_uploaded_base(monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    monkeypatch.setattr(g, "_comfy_upload", lambda cfg, png: "base.png")
    f = Fake()
    assert g.img2img({**CFG, "checkpoint": "mine.safetensors"}, "smile", b"x", 3, f) == PNG
    graph = next(b for u, b in f.calls if u.endswith("/prompt"))["prompt"]
    assert graph["8"]["inputs"]["image"] == "base.png" and graph["4"]["class_type"] == "VAEEncode"
    assert graph["5"]["inputs"]["denoise"] == CFG["denoise"] and graph["1"]["inputs"]["ckpt_name"] == "mine.safetensors"


def test_timeout_is_reported(monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    try:
        g.txt2img({**CFG, "timeout": 3}, "p", 1, Fake(ready_after=99))
        assert False
    except RuntimeError as e:
        assert "did not finish" in str(e)


def test_custom_workflow_placeholders(tmp_path, monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    wf = tmp_path / "w.json"
    wf.write_text(json.dumps({"1": {"class_type": "X", "inputs": {"seed": "{{seed}}", "text": "{{prompt}}, soft", "w": "{{width}}"}}}))
    f = Fake()
    g.txt2img({**CFG, "workflow": str(wf)}, "hello", 5, f)
    node = next(b for u, b in f.calls if u.endswith("/prompt"))["prompt"]["1"]["inputs"]
    assert node == {"seed": 5, "text": "hello, soft", "w": CFG["width"]}


def test_pack_never_overwrites_outside_its_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    monkeypatch.setattr(g, "_comfy_upload", lambda cfg, png: "b.png")
    monkeypatch.setattr(g, "remove_flat_background", lambda p: p)
    res = g.generate_pack({"name": "t"}, CFG, str(tmp_path / "pack"), expressions=["idle", "happy"], fetch=Fake(ready_after=1))
    assert res["made"] == ["idle", "happy"] and (tmp_path / "pack" / "happy.png").exists()
