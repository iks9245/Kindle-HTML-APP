import json
import os
from datetime import date, datetime, timedelta

_HERE = os.path.dirname(__file__)
STATE_PATH = os.path.join(_HERE, "..", ".digest-state", "seen.json")


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
