import io
import os

import numpy as np
from PIL import Image

from utils import avatar, avatar_gen, speaking


def _png(arr):
    b = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(b, "PNG")
    return b.getvalue()


def _scene():
    a = np.zeros((60, 60, 4), dtype=np.uint8)
    a[:, :] = (250, 200, 210, 255)
    a[15:45, 15:45] = (40, 40, 120, 255)
    a[14, 15:45] = (205, 170, 195, 255)         # anti-aliased fringe row
    return a


def test_background_is_cut_and_fringe_is_soft():
    out = np.array(Image.open(io.BytesIO(avatar_gen.remove_flat_background(_png(_scene())))))
    assert out[0, 0, 3] == 0 and out[30, 30, 3] == 255
    assert 0 < out[14, 30, 3] < 255                # soft edge, not a hard cut


def test_hard_cut_when_feather_off():
    out = np.array(Image.open(io.BytesIO(avatar_gen.remove_flat_background(_png(_scene()), feather=False))))
    assert set(np.unique(out[:, :, 3])) <= {0, 255}


def test_clean_pack_keeps_originals(tmp_path):
    d = tmp_path / "look"
    d.mkdir()
    (d / "idle.png").write_bytes(_png(_scene()))
    r = avatar_gen.clean_pack(str(d))
    assert r == {"done": 1, "failed": 0}
    assert (d / "_original" / "idle.png").exists()
    avatar_gen.clean_pack(str(d))                  # second run starts from the original again
    assert np.array(Image.open(d / "idle.png"))[0, 0, 3] == 0


def test_is_opaque(tmp_path):
    p = tmp_path / "idle.png"
    p.write_bytes(_png(_scene()))
    assert avatar.is_opaque(str(p)) is True
    p.write_bytes(avatar_gen.remove_flat_background(_png(_scene())))
    os.utime(p, (os.path.getmtime(p) + 5, os.path.getmtime(p) + 5))
    assert avatar.is_opaque(str(p)) is False


def test_caption_sanitiser():
    t = speaking.clean_caption("cảm ơn 𝓪𝓷𝓷 😀 đã tặng   Doughnut!")
    assert "😀" not in t and "  " not in t and "Doughnut!" in t and "ann" in t and "cảm ơn" in t
