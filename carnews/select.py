"""Select which stories become posts (EV-performance + wagon aware)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .feeds import CONFIG

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "posts" / "_posted.json"


def _word_hit(hay: str, term: str) -> bool:
    if " " in term:
        return term in hay
    return re.search(rf"\b{re.escape(term)}\b", hay) is not None


def _hay(it: dict) -> str:
    return f"{it['title']} {it.get('excerpt','')} {' '.join(it.get('categories', []))}".lower()


def tag_topics(items: list) -> None:
    ev = [t.lower() for t in CONFIG["evPerformance"]["evTerms"]]
    perf = [t.lower() for t in CONFIG["evPerformance"]["perfTerms"]]
    wagon = [t.lower() for t in CONFIG.get("wagon", {}).get("terms", [])]
    for it in items:
        h = _hay(it)
        it["ev_performance"] = any(_word_hit(h, t) for t in ev) and any(_word_hit(h, t) for t in perf)
        it["wagon"] = any(_word_hit(h, t) for t in wagon)


def tag_ev_performance(items: list) -> None:
    tag_topics(items)


def _load_posted() -> set:
    if HISTORY.exists():
        try:
            return set(json.loads(HISTORY.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def mark_posted(links: list) -> None:
    posted = _load_posted() | set(links)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(sorted(posted), indent=2), encoding="utf-8")


def select_batch(items: list, count: int = 3, ensure_ev: bool = True, ensure_wagon: bool = True) -> list:
    tag_topics(items)
    posted = _load_posted()
    fresh = [it for it in items if it["link"] not in posted]
    chosen, used = [], set()

    def take_first(pred):
        for it in fresh:
            if it not in chosen and pred(it):
                chosen.append(it); used.add(it["source_id"]); return True
        return False

    if ensure_ev:
        take_first(lambda it: it.get("ev_performance"))
    if ensure_wagon and len(chosen) < count:
        take_first(lambda it: it.get("wagon"))
    for it in fresh:
        if len(chosen) >= count: break
        if it in chosen or it["source_id"] in used: continue
        chosen.append(it); used.add(it["source_id"])
    for it in fresh:
        if len(chosen) >= count: break
        if it not in chosen: chosen.append(it)
    return chosen[:count]
