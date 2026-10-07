import json
import random

from utils import returning


def test_new_then_returning(tmp_path):
    b = returning.ViewerBook(str(tmp_path / "v.json"), gap_hours=6)
    assert b.visit("Lan", now=1000) == 0
    assert b.visit("Lan", now=1000 + 60) == 0                 # same visit (app refresh)
    assert b.visit("lan ", now=1000 + 7 * 3600) == 1          # case/space-insensitive, a real return
    assert b.visit("Lan", now=1000 + 14 * 3600) == 2


def test_names_never_stored(tmp_path):
    p = tmp_path / "v.json"
    b = returning.ViewerBook(str(p))
    b.visit("Nguyễn Văn A", now=1)
    raw = p.read_text(encoding="utf-8")
    assert "Nguy" not in raw and "Van" not in raw
    assert returning.ViewerBook(str(p)).count() == 1          # persists


def test_forget_all(tmp_path):
    p = tmp_path / "v.json"
    b = returning.ViewerBook(str(p))
    b.visit("A", now=1)
    b.forget_all()
    assert b.count() == 0 and not p.exists()
    assert b.visit("A", now=10 ** 6) == 0


def test_greeting():
    rng = random.Random(1)
    assert returning.greeting("Lan", 0, rng) is None
    assert "Lan" in returning.greeting("Lan", 1, rng)
    assert returning.greeting("", 2, rng) is None
    assert "Lan" in returning.greeting("Lan", 5, rng)
