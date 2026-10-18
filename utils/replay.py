"""Replay timeline of a finished live, built only from the logged events (pure, tested).

Minute-by-minute rows (comments, questions, gifts, joins, answers, handoffs) plus the peak minute and the quiet stretches, so
the seller can see where the live took off or died. Viewers are never named; the log stores only hashed ids."""
from typing import Dict, Iterable, List

QUESTION_INTENTS = {"buy", "price", "stock", "options", "shipping", "trust", "return", "usage"}


def build(events: Iterable[Dict], bucket_s: int = 60) -> Dict:
    ev = [e for e in events if e.get("ts") is not None]
    if not ev:
        return {"rows": [], "peak": None, "quiet": [], "bucket_s": bucket_s}
    t0 = float(ev[0]["ts"])
    n = int((float(ev[-1]["ts"]) - t0) // bucket_s) + 1
    rows: List[Dict] = [{"i": i, "min": round(i * bucket_s / 60, 1), "comments": 0, "questions": 0, "gifts": 0, "joins": 0,
                         "answers": 0, "handoffs": 0, "pitches": 0} for i in range(n)]
    for e in ev:
        r = rows[int((float(e["ts"]) - t0) // bucket_s)]
        k = e.get("kind")
        if k == "comment":
            r["comments"] += 1
            if e.get("intent") in QUESTION_INTENTS:
                r["questions"] += 1
        elif k == "gift":
            r["gifts"] += 1
        elif k == "entrance":
            r["joins"] += 1
        elif k == "answer":
            r["answers"] += 1
        elif k == "handoff":
            r["handoffs"] += 1
        elif k == "pitch":
            r["pitches"] += 1
    score = lambda r: r["comments"] + 3 * r["gifts"] + r["joins"] * 0.5
    best = max(rows, key=score)
    peak = {"min": best["min"], "comments": best["comments"], "gifts": best["gifts"]} if score(best) > 0 else None
    quiet, run = [], []
    for r in rows:
        if r["comments"] == 0 and r["gifts"] == 0:
            run.append(r["min"])
        else:
            if len(run) >= 3:
                quiet.append({"from": run[0], "to": run[-1] + bucket_s / 60})
            run = []
    if len(run) >= 3:
        quiet.append({"from": run[0], "to": run[-1] + bucket_s / 60})
    return {"rows": rows, "peak": peak, "quiet": quiet, "bucket_s": bucket_s}


def markdown(tl: Dict) -> str:
    if not tl["rows"]:
        return "No events logged for this live."
    out = ["| Minute | Comments | Questions | Gifts | Joins | Answers | Handoffs |", "|---|---|---|---|---|---|---|"]
    for r in tl["rows"]:
        out.append(f"| {r['min']:g} | {r['comments']} | {r['questions']} | {r['gifts']} | {r['joins']} | {r['answers']} | {r['handoffs']} |")
    if tl["peak"]:
        out.append(f"\nBusiest minute: {tl['peak']['min']:g} ({tl['peak']['comments']} comments, {tl['peak']['gifts']} gifts).")
    for q in tl["quiet"]:
        out.append(f"Quiet stretch: minute {q['from']:g} to {q['to']:g} (no comments or gifts).")
    return "\n".join(out)
