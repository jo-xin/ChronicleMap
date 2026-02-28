from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LOCALE = "en"
FALLBACK_LOCALE = "en"
CURRENT_LOCALE = DEFAULT_LOCALE

_LOCALES_DIR = Path(__file__).with_name("locales")
_TEXT_CACHE: dict[str, dict[str, str]] = {}


def _load_locale(locale: str) -> dict[str, str]:
    if locale in _TEXT_CACHE:
        return _TEXT_CACHE[locale]
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        _TEXT_CACHE[locale] = {}
        return _TEXT_CACHE[locale]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _TEXT_CACHE[locale] = {str(k): str(v) for k, v in data.items()}
        else:
            _TEXT_CACHE[locale] = {}
    except Exception:
        _TEXT_CACHE[locale] = {}
    return _TEXT_CACHE[locale]


def list_locales() -> list[str]:
    if not _LOCALES_DIR.exists():
        return [DEFAULT_LOCALE]
    return sorted(p.stem for p in _LOCALES_DIR.glob("*.json"))


def set_locale(locale: str) -> str:
    global CURRENT_LOCALE
    available = set(list_locales())
    if locale in available:
        CURRENT_LOCALE = locale
    elif DEFAULT_LOCALE in available:
        CURRENT_LOCALE = DEFAULT_LOCALE
    else:
        CURRENT_LOCALE = locale
    return CURRENT_LOCALE


def get_locale() -> str:
    return CURRENT_LOCALE


def tr(key: str, **kwargs: Any) -> str:
    locale_map = _load_locale(CURRENT_LOCALE)
    fallback_map = _load_locale(FALLBACK_LOCALE)
    template = locale_map.get(key) or fallback_map.get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
