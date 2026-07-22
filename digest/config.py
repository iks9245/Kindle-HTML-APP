import os

import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

_DEFAULTS = {
    "language": "zh-TW",
    "timezone": "UTC",
    "max_articles_per_feed": 5,
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "openai_base_url": None,
    "feeds": [],
}


def load_config(path: str | None = None) -> dict:
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f) or {}
    for key, value in _DEFAULTS.items():
        conf.setdefault(key, value)
    return conf
