"""
Apply a locale pack (e.g. data/locale_vi.json) to config.json so the streamer SPEAKS that language.
The code base and web UI stay English; only spoken strings (templates, trigger words, prompts) change.

    python apply_locale.py data/locale_vi.json            # edits config.json (backup: config.json.before_locale)
    python apply_locale.py data/locale_vi.json --dry-run  # just list what would change
"""
import argparse
import json
import shutil
import sys


def set_path(node, path, value):
    parts = path.split("/")
    for p in parts[:-1]:
        node = node[int(p)] if isinstance(node, list) else node[p]
    last = parts[-1]
    if isinstance(node, list):
        i = int(last)
        if i >= len(node):
            return False
        node[i] = value
    else:
        if last not in node:
            return False
        node[last] = value
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("locale")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with open(args.locale, encoding="utf-8") as f:
        values = json.load(f)["values"]
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    applied, missing = 0, []
    for path, value in values.items():
        try:
            ok = set_path(cfg, path, value)
        except (KeyError, IndexError, ValueError):
            ok = False
        if ok:
            applied += 1
        else:
            missing.append(path)
    print(f"{applied} values applied, {len(missing)} paths not present in config")
    for m in missing:
        print("  missing:", m)
    if args.dry_run:
        return
    shutil.copyfile(args.config, args.config + ".before_locale")
    with open(args.config, "w", encoding="utf-8", newline="") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("config written; backup at", args.config + ".before_locale")


if __name__ == "__main__":
    sys.exit(main())
