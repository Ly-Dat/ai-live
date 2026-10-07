import os
import sys
import time
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import product_tour  # noqa: E402
from utils import product_catalog, tiktok_safety  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "products.json")
TPL = os.path.join(ROOT, "data", "pitch_templates.json")
TERMS = os.path.join(ROOT, "data", "tiktok_policy_terms.json")


def _catalog():
    return product_catalog.ProductCatalog(FIX, TPL)


def test_seller_intro_line_is_spoken_right_after_template_intro():
    c = _catalog()
    p = dict(c.all_products()[0], intro="Cai nay minh tu dung, ben lam.")
    pitch = c.build_pitch(p, 0)
    assert "Cai nay minh tu dung, ben lam." in pitch
    sents = product_tour.split_sentences(pitch)
    assert sents.index("Cai nay minh tu dung, ben lam.") <= 2


def test_no_intro_means_nothing_extra():
    c = _catalog()
    p = dict(c.all_products()[0], intro="")
    assert "None" not in c.build_pitch(p, 0)


def test_script_repeats_until_time_is_up_and_stops(monkeypatch):
    c = _catalog()
    p = dict(c.all_products()[0], duration_min=0.05)  # 3 s, about two cycles at 0.15 s per line
    safety = tiktok_safety.TikTokSafety(TERMS)
    spoken = []

    def fake_say(args, text):
        spoken.append(text)
        time.sleep(0.15)
    monkeypatch.setattr(product_tour, "say", fake_say)
    args = types.SimpleNamespace(min_minutes=5, max_minutes=10, reply_wait=0.0, quiet=0.0)
    product_tour.STATE.last_comment = 0.0
    t0 = time.time()
    product_tour.present_product(args, c, safety, p, 0)
    assert 2.5 < time.time() - t0 < 5.0          # ran for about its time slot, then moved on
    one_cycle = len(product_tour.build_segments(c, p, 0, safety))
    assert len(spoken) > one_cycle                 # script repeated (comment-free) until the slot ended


def test_comment_makes_the_host_wait_then_resume(monkeypatch):
    args = types.SimpleNamespace(reply_wait=0.3, quiet=0.2)
    product_tour.STATE.mark()
    t0 = time.time()
    product_tour.wait_until_free(args)
    assert 0.4 < time.time() - t0 < 1.5            # held back reply_wait + quiet, then free
