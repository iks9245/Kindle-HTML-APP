import json
import os
from datetime import date, datetime, timedelta

_HERE = os.path.dirname(__file__)
_STATE_DIR = os.path.join(_HERE, "..", ".digest-state")
STATE_PATH = os.path.join(_STATE_DIR, "seen.json")
# Per-day snapshots of the articles shown, keyed by date. Used to build the
# next day's recall quiz from what the reader saw previously.
RECENT_PATH = os.path.join(_STATE_DIR, "recent.json")


def load_seen() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict, retention_days: int) -> None:
    if retention_days and retention_days > 0:
        cutoff = date.today() - timedelta(days=retention_days)
        seen = {
            link: seen_date
            for link, seen_date in seen.items()
            if datetime.strptime(seen_date, "%Y-%m-%d").date() >= cutoff
        }
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)


def load_recent() -> dict:
    if not os.path.exists(RECENT_PATH):
        return {}
    with open(RECENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_recent(recent: dict, retention_days: int) -> None:
    if retention_days and retention_days > 0:
        cutoff = date.today() - timedelta(days=retention_days)
        recent = {
            day: items
            for day, items in recent.items()
            if _parse_date(day) is not None and _parse_date(day) >= cutoff
        }
    os.makedirs(_STATE_DIR, exist_ok=True)
    with open(RECENT_PATH, "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False, indent=2, sort_keys=True)


def _parse_date(day: str):
    try:
        return datetime.strptime(day, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
