from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup

from app.auth import LANG_COOKIE
from app.i18n import DEFAULT, SUPPORTED, normalize, translator

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# All times shown in Tashkent (UTC+5, no DST).
TASHKENT = ZoneInfo("Asia/Tashkent")

# html=False prevents raw HTML in markdown source (admin is trusted, but defense-in-depth).
_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": True}).enable("table")


def _format_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TASHKENT).strftime("%Y-%m-%d %H:%M (UTC+5)")


def _to_iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _tashkent_local(dt: datetime | None) -> str:
    """For <input type=datetime-local>: 'YYYY-MM-DDTHH:MM' in Tashkent time, no tz."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TASHKENT).strftime("%Y-%m-%dT%H:%M")


def _format_score(value: float | None, digits: int = 5) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _render_markdown(value: str | None) -> Markup:
    return Markup(_md.render(value or ""))


templates.env.filters["dt"] = _format_dt
templates.env.filters["iso"] = _to_iso
templates.env.filters["tashkent_local"] = _tashkent_local
templates.env.filters["score"] = _format_score
templates.env.filters["md"] = _render_markdown


def get_lang(request: Request) -> str:
    return normalize(request.cookies.get(LANG_COOKIE) or DEFAULT)


def description_for(competition, lang: str) -> str:
    """Pick localized description with fallback chain: lang -> ru -> en -> uz -> legacy."""
    if competition is None:
        return ""
    chain = [lang, "ru", "en", "uz"]
    seen = set()
    for code in chain:
        if code in seen:
            continue
        seen.add(code)
        text = getattr(competition, f"description_{code}", "") or ""
        if text.strip():
            return text
    return getattr(competition, "description", "") or ""


def render(request: Request, template: str, context: dict | None = None):
    lang = get_lang(request)
    ctx = {
        "request": request,
        "t": translator(lang),
        "lang": lang,
        "supported_langs": SUPPORTED,
        "now": datetime.now(timezone.utc),
        "description_for": description_for,
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(template, ctx)
