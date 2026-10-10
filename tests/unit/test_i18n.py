"""The EN/VI switch: dictionary shape and the generated script."""
import json
import os
import re

from utils import i18n


def _d():
    with open(os.path.join(i18n.HERE, "vi.json"), encoding="utf8") as f:
        return json.load(f)


def test_dictionary_shape():
    d = _d()
    assert len(d["exact"]) > 1500
    assert d["exact"]["Disabled"] == "Tắt"
    for k, v in d["exact"].items():
        assert k and v
        assert k.count("{") == v.count("{"), k


def test_templates_compile_and_keep_group_count():
    for pat, out in _d()["re"]:
        groups = re.compile(pat).groups
        used = {int(x) for x in re.findall(r"\$(\d+)", out)}
        assert used and max(used) <= groups, (pat, out)


def test_script_has_switch_and_url():
    html = i18n.body_html()
    assert "lvToggleLang" in html and "/lv_i18n/vi.json" in html and "__" not in html.replace("__proto__", "")

