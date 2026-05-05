from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.auth import LANG_COOKIE
from app.i18n import DEFAULT, SUPPORTED, normalize, translator

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _format_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_score(value: float | None, digits: int = 5) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


templates.env.filters["dt"] = _format_dt
templates.env.filters["score"] = _format_score


def get_lang(request: Request) -> str:
    return normalize(request.cookies.get(LANG_COOKIE) or DEFAULT)


def render(request: Request, template: str, context: dict | None = None):
    lang = get_lang(request)
    ctx = {
        "request": request,
        "t": translator(lang),
        "lang": lang,
        "supported_langs": SUPPORTED,
        "now": datetime.now(timezone.utc),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(template, ctx)
