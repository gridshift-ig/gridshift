"""Select which stories become posts, bucketed into 3 categories.

Categories (config in feeds.json -> "categories"):
  performance  Performance car reviews, ICE + EV
  racing       Motorsport / race coverage
  wagon        Wagons / estates / longroofs

A daily batch is one post per category (3 total). The workflow runs the
batch twice a day -> 6 posts/day, ~2 per category. When racing or wagon
have nothing fresh, the slot is BACKFILLED with an extra performance pick
so the account still posts a full batch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .feeds import CONFIG

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "posts" / "_posted.json"

CATS = CONFIG.get("categories", {})
ORDER = CATS.get("_order", ["racing", "wagon", "performance"])
BACKFILL = CATS.get("_backfill", "performance")
# Category slots a daily batch tries to fill, in display order.
SLOTS = ["performance", "racing", "wagon"]


def _word_hit(hay: str, term: str) -> bool:
    if " " in term or "-" in term:
        return term in hay
    return re.search(rf"\b{re.escape(term)}\b", hay) is not None


def _hay(it: dict) -> str:
    return f"{it['title']} {it.get('excerpt','')} {' '.join(it.get('categories', []))}".lower()


def _terms(cat: str) -> list:
    return [t.lower() for t in CATS.get(cat, {}).get("terms", [])]


def categorize(items: list) -> None:
    """Assign each item a single primary category (it['category']).

    Precedence is CATS['_order'] (default racing > wagon > performance):
    racing is event-specific, wagon is body-style-specific, performance is
    the broad catch-all. Items matching nothing get category None.
    """
    term_map = {c: _terms(c) for c in CATS if not c.startswith("_")}
    for it in items:
        h = _hay(it)
        matched = [c for c, terms in term_map.items() if any(_word_hit(h, t) for t in terms)]
        it["categories_matched"] = matched
        cat = None
        for c in ORDER:
            if c in matched:
                cat = c
                break
        it["category"] = cat
        # Back-compat flags some older code/manifests may read.
        it["ev_performance"] = cat == "performance"
        it["wagon"] = cat == "wagon"


# Back-compat aliases for any caller importing the old names.
def tag_topics(items: list) -> None:
    categorize(items)


def tag_ev_performance(items: list) -> None:
    categorize(items)


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


def select_category_batch(items: list, count: int = 3) -> list:
    """Pick one fresh story per category slot, backfilling empties.

    For each slot in SLOTS we take the first fresh, source-diverse story in
    that category. If none, we backfill with a BACKFILL-category pick, then
    with any fresh story. Extra slots beyond the 3 categories (count > 3)
    are filled from the backfill pool, then anything fresh.
    """
    categorize(items)
    posted = _load_posted()
    fresh = [it for it in items if it["link"] not in posted]
    chosen: list = []
    used_sources: set = set()

    def take(pred) -> bool:
        # First pass favors source diversity; second pass relaxes it.
        for diverse in (True, False):
            for it in fresh:
                if it in chosen:
                    continue
                if diverse and it["source_id"] in used_sources:
                    continue
                if pred(it):
                    chosen.append(it)
                    used_sources.add(it["source_id"])
                    return True
        return False

    slots = list(SLOTS)
    while len(slots) < count:
        slots.append(BACKFILL)
    slots = slots[:count]

    for slot in slots:
        if take(lambda it, s=slot: it.get("category") == s):
            continue
        if take(lambda it: it.get("category") == BACKFILL):
            continue
        take(lambda it: True)

    return chosen[:count]


# Back-compat: old signature used by anything still calling select_batch().
def select_batch(items: list, count: int = 3, ensure_ev: bool = True,
                 ensure_wagon: bool = True) -> list:
    return select_category_batch(items, count=count)
