"""Select which stories become posts, bucketed into 3 categories.

Categories (config in feeds.json -> "categories"):
  performance  Performance car reviews, ICE + EV
  racing       Motorsport / race coverage
  wagon        Wagons / estates / longroofs

The workflow runs once every 3 hours (24/7) and posts ONE story per run,
rotating performance -> racing -> wagon across runs (see generate.py
--category auto). Empty racing/wagon slots are BACKFILLED with a
performance pick so every run still posts.

Pickup-truck stories are removed up front by filter_trucks() per the
feeds.json "truck_filter" block (default: drop ICE trucks, keep EV trucks).
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
# Category rotation order for single-post runs and multi-slot batches.
SLOTS = ["performance", "racing", "wagon"]


def _word_hit(hay: str, term: str) -> bool:
    if " " in term or "-" in term:
        return term in hay
    return re.search(rf"\b{re.escape(term)}\b", hay) is not None


def _hay(it: dict) -> str:
    return f"{it['title']} {it.get('excerpt','')} {' '.join(it.get('categories', []))}".lower()


def _terms(cat: str) -> list:
    return [t.lower() for t in CATS.get(cat, {}).get("terms", [])]


# --- Truck filter -----------------------------------------------------------
TRUCK_FILTER = CONFIG.get("truck_filter", {})


def _is_truck(hay: str) -> bool:
    terms = [t.lower() for t in TRUCK_FILTER.get("truck_terms", [])]
    return any(_word_hit(hay, t) for t in terms)


def _is_ev(hay: str) -> bool:
    terms = [t.lower() for t in TRUCK_FILTER.get("ev_terms", [])]
    return any(_word_hit(hay, t) for t in terms)


def filter_trucks(items: list) -> list:
    """Drop pickup-truck stories per feeds.json -> truck_filter.

    mode 'ice_only' (default): drop trucks with no EV signal, keep EV trucks.
    mode 'all': drop every truck regardless of powertrain.
    mode 'off' / anything else: no filtering.
    Each dropped item is flagged it['filtered_out'] = 'ice_truck' | 'truck'.
    """
    mode = TRUCK_FILTER.get("mode", "off")
    if mode not in ("ice_only", "all"):
        return items
    kept: list = []
    for it in items:
        h = _hay(it)
        if _is_truck(h):
            if mode == "all":
                it["filtered_out"] = "truck"
                continue
            if not _is_ev(h):  # ice_only: gas truck -> drop
                it["filtered_out"] = "ice_truck"
                continue
        kept.append(it)
    return kept


# --- Categorization ---------------------------------------------------------
def categorize(items: list) -> None:
    """Assign each item a single primary category (it['category']).

    Precedence is CATS['_order'] (default racing > wagon > performance):
    racing is event-specific, wagon is body-style-specific, performance is
    the broad catch-all. Items matching nothing get category None.
    """
    term_map = {c: _terms(c) for c in CATS if not c.startswith("_")}
    for it in items:
        h = _hay(it)
        # Wagon is high-precision: only count a story as a wagon if the
        # HEADLINE itself names it one (wagon/estate/avant/longroof/etc.).
        # Matching the body/excerpt pulled in non-wagons (supercars, SUV
        # "variants", concept "caravans", V8 round-ups that merely mention
        # wagons), so wagon matches the title only.
        title_h = (it.get("title", "") or "").lower()
        matched = []
        for c, terms in term_map.items():
            hay = title_h if c == "wagon" else h
            if any(_word_hit(hay, t) for t in terms):
                matched.append(c)
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


def select_for_slots(items: list, slots: list) -> list:
    """Fill an ordered list of category slots with fresh, source-diverse picks.

    Each slot takes the first fresh story of that category. If none is
    available, the slot is backfilled with a BACKFILL-category pick, then
    with any fresh story, so every slot is filled when content exists.
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

    for slot in slots:
        if take(lambda it, s=slot: it.get("category") == s):
            continue
        if take(lambda it: it.get("category") == BACKFILL):
            continue
        take(lambda it: True)

    return chosen


def select_one(items: list, category: str) -> list:
    """Pick a single fresh post of `category` (perf/any backfill)."""
    return select_for_slots(items, [category])[:1]


def select_category_batch(items: list, count: int = 3) -> list:
    """Pick `count` posts, one per category slot, padding with backfill slots."""
    slots = list(SLOTS)
    while len(slots) < count:
        slots.append(BACKFILL)
    slots = slots[:count]
    return select_for_slots(items, slots)[:count]


# Back-compat: old signature used by anything still calling select_batch().
def select_batch(items: list, count: int = 3, ensure_ev: bool = True,
                 ensure_wagon: bool = True) -> list:
    return select_category_batch(items, count=count)
