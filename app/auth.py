from __future__ import annotations

import re

import bcrypt
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import settings

PARTICIPANT_COOKIE = "participant_session"
ADMIN_COOKIE = "admin_session"
LANG_COOKIE = "lang"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeSerializer(settings.secret_key, salt="leaderboard")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def normalize_identity(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def set_participant_cookie(response: Response, participant_id: int) -> None:
    token = _serializer.dumps({"pid": participant_id})
    response.set_cookie(
        PARTICIPANT_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def get_participant_id(request: Request) -> int | None:
    token = request.cookies.get(PARTICIPANT_COOKIE)
    if not token:
        return None
    try:
        data = _serializer.loads(token)
        return int(data.get("pid"))
    except (BadSignature, ValueError, TypeError):
        return None


def clear_participant_cookie(response: Response) -> None:
    response.delete_cookie(PARTICIPANT_COOKIE)


def set_admin_cookie(response: Response, admin_id: int) -> None:
    token = _serializer.dumps({"aid": admin_id})
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def get_admin_id(request: Request) -> int | None:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return None
    try:
        data = _serializer.loads(token)
        return int(data.get("aid"))
    except (BadSignature, ValueError, TypeError):
        return None


def clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_COOKIE)
