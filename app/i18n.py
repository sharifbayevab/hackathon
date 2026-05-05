import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED = ("uz", "ru", "en")
DEFAULT = "uz"

_cache: dict[str, dict[str, str]] = {}


def _load(lang: str) -> dict[str, str]:
    if lang not in _cache:
        path = LOCALES_DIR / f"{lang}.json"
        with path.open(encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def normalize(lang: str | None) -> str:
    if not lang:
        return DEFAULT
    lang = lang.lower()[:2]
    return lang if lang in SUPPORTED else DEFAULT


def translator(lang: str):
    lang = normalize(lang)
    primary = _load(lang)
    fallback = _load(DEFAULT)

    def t(key: str, **kwargs) -> str:
        msg = primary.get(key) or fallback.get(key) or key
        if kwargs:
            try:
                return msg.format(**kwargs)
            except (KeyError, IndexError):
                return msg
        return msg

    return t
