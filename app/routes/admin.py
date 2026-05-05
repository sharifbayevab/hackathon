from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

TASHKENT = ZoneInfo("Asia/Tashkent")

from app.auth import (
    clear_admin_cookie,
    get_admin_id,
    set_admin_cookie,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.i18n import translator
from app.models import (
    AdminUser,
    Competition,
    Metric,
    Participant,
    Submission,
    SubmissionStatus,
)
from app.scoring import ScoringError, load_groundtruth, score_submission
from app.services import get_active_competition
from app.templating import get_lang, render

router = APIRouter(prefix="/admin")


def _require_admin(request: Request, db: Session) -> AdminUser:
    aid = get_admin_id(request)
    if aid is None:
        raise HTTPException(303, headers={"Location": "/admin/login"})
    admin = db.get(AdminUser, aid)
    if admin is None:
        raise HTTPException(303, headers={"Location": "/admin/login"})
    return admin


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    if get_admin_id(request) is not None:
        return RedirectResponse("/admin", status_code=303)
    return render(request, "admin/login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    t = translator(get_lang(request))
    stmt = select(AdminUser).where(AdminUser.username == username.strip())
    admin = db.scalars(stmt).first()
    if not admin or not verify_password(password, admin.password_hash):
        return render(request, "admin/login.html", {"error": t("invalid_credentials")})
    response = RedirectResponse("/admin", status_code=303)
    set_admin_cookie(response, admin.id)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    clear_admin_cookie(response)
    return response


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = _require_admin(request, db)
    competition = get_active_competition(db)
    total_subs = 0
    total_participants = 0
    if competition:
        total_subs = db.scalar(
            select(func.count(Submission.id)).where(Submission.competition_id == competition.id)
        ) or 0
        total_participants = db.scalar(
            select(func.count(distinct(Submission.participant_id))).where(
                Submission.competition_id == competition.id
            )
        ) or 0
    return render(
        request,
        "admin/dashboard.html",
        {
            "admin": admin,
            "competition": competition,
            "metrics": [m.value for m in Metric],
            "total_submissions": total_subs,
            "total_participants": total_participants,
            "flash": request.query_params.get("flash"),
        },
    )


def _parse_deadline(raw: str | None) -> datetime | None:
    """Parse `<input type=datetime-local>` value as Tashkent local time."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TASHKENT)
    return dt.astimezone(timezone.utc)


async def _read_md(upload: UploadFile | None) -> str | None:
    if upload is None or not upload.filename:
        return None
    raw = await upload.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, f"{upload.filename}: file is not valid UTF-8")


@router.post("/competition")
async def upsert_competition(
    request: Request,
    title: str = Form(""),
    metric: str = Form(Metric.accuracy.value),
    deadline: str = Form(""),
    id_column: str = Form("id"),
    answer_column: str = Form("answer"),
    is_active: str = Form("on"),
    train_file: UploadFile | None = File(None),
    sample_file: UploadFile | None = File(None),
    description_uz_file: UploadFile | None = File(None),
    description_ru_file: UploadFile | None = File(None),
    description_en_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    if metric not in {m.value for m in Metric}:
        raise HTTPException(400, "Invalid metric")

    competition = get_active_competition(db)
    if competition is None:
        competition = Competition()
        db.add(competition)

    competition.title = title.strip()
    competition.metric = metric
    competition.deadline = _parse_deadline(deadline)
    competition.id_column = (id_column.strip() or "id")
    competition.answer_column = (answer_column.strip() or "answer")
    competition.is_active = is_active == "on"

    uz = await _read_md(description_uz_file)
    ru = await _read_md(description_ru_file)
    en = await _read_md(description_en_file)
    if uz is not None:
        competition.description_uz = uz
    if ru is not None:
        competition.description_ru = ru
    if en is not None:
        competition.description_en = en

    db.flush()

    if train_file is not None and train_file.filename:
        dst = settings.assets_dir / f"train_{competition.id}.csv"
        with dst.open("wb") as out:
            shutil.copyfileobj(train_file.file, out)
        competition.train_path = str(dst)

    if sample_file is not None and sample_file.filename:
        dst = settings.assets_dir / f"sample_{competition.id}.csv"
        with dst.open("wb") as out:
            shutil.copyfileobj(sample_file.file, out)
        competition.sample_submission_path = str(dst)

    db.commit()
    return RedirectResponse("/admin?flash=saved", status_code=303)


@router.post("/groundtruth")
async def upload_groundtruth(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    competition = get_active_competition(db)
    if competition is None:
        raise HTTPException(400, "Create the task first")

    settings.groundtruth_dir.mkdir(parents=True, exist_ok=True)
    dst = settings.groundtruth_dir / f"groundtruth_{competition.id}.csv"
    with dst.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        gt = load_groundtruth(dst, competition.id_column, competition.answer_column)
    except ScoringError as e:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, f"Invalid groundtruth: {e}")

    competition.groundtruth_path = str(dst)
    db.commit()

    public_n = int((gt["split"] == "public").sum())
    private_n = int((gt["split"] == "private").sum())
    return RedirectResponse(
        f"/admin?flash=gt_uploaded&public={public_n}&private={private_n}", status_code=303
    )


@router.post("/rescore")
def rescore_all(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    competition = get_active_competition(db)
    if competition is None or not competition.groundtruth_path:
        raise HTTPException(400, "No competition or groundtruth")

    gt = load_groundtruth(
        Path(competition.groundtruth_path), competition.id_column, competition.answer_column
    )
    metric = Metric(competition.metric)

    stmt = select(Submission).where(Submission.competition_id == competition.id)
    for sub in db.scalars(stmt).all():
        try:
            result = score_submission(
                Path(sub.file_path), gt, metric, competition.id_column, competition.answer_column
            )
            sub.public_score = result.public
            sub.private_score = result.private
            sub.status = SubmissionStatus.scored.value
            sub.error_message = None
        except ScoringError as e:
            sub.status = SubmissionStatus.failed.value
            sub.error_message = str(e)
            sub.public_score = None
            sub.private_score = None
    db.commit()
    return RedirectResponse("/admin?flash=rescored", status_code=303)


@router.get("/submissions")
def submissions_list(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    competition = get_active_competition(db)
    items: list[tuple[Submission, Participant]] = []
    if competition:
        stmt = (
            select(Submission, Participant)
            .join(Participant, Submission.participant_id == Participant.id)
            .where(Submission.competition_id == competition.id)
            .order_by(Submission.created_at.desc())
            .limit(500)
        )
        items = list(db.execute(stmt).all())
    return render(
        request,
        "admin/submissions.html",
        {"competition": competition, "items": items},
    )


@router.post("/submissions/{submission_id}/delete")
def delete_submission(submission_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(404)
    file_path = sub.file_path
    db.delete(sub)
    db.commit()
    Path(file_path).unlink(missing_ok=True)
    return RedirectResponse("/admin/submissions", status_code=303)


@router.post("/submissions/clear")
def clear_all_submissions(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    competition = get_active_competition(db)
    if competition is None:
        return RedirectResponse("/admin/submissions", status_code=303)

    paths = list(
        db.scalars(
            select(Submission.file_path).where(Submission.competition_id == competition.id)
        ).all()
    )
    db.execute(delete(Submission).where(Submission.competition_id == competition.id))
    db.commit()

    for p in paths:
        Path(p).unlink(missing_ok=True)

    return RedirectResponse("/admin/submissions?flash=cleared", status_code=303)


@router.post("/reset")
def reset_everything(
    request: Request,
    confirm: str = Form(""),
    db: Session = Depends(get_db),
):
    """Wipe everything except the admin account, ready for a new task."""
    _require_admin(request, db)
    if confirm.strip().upper() != "RESET":
        return RedirectResponse("/admin?flash=reset_cancelled", status_code=303)

    sub_paths = list(db.scalars(select(Submission.file_path)).all())
    db.execute(delete(Submission))
    db.execute(delete(Participant))
    db.execute(delete(Competition))
    db.commit()

    for p in sub_paths:
        Path(p).unlink(missing_ok=True)
    for p in settings.assets_dir.glob("train_*.csv"):
        p.unlink(missing_ok=True)
    for p in settings.assets_dir.glob("sample_*.csv"):
        p.unlink(missing_ok=True)
    for p in settings.groundtruth_dir.glob("groundtruth_*.csv"):
        p.unlink(missing_ok=True)

    return RedirectResponse("/admin?flash=reset_done", status_code=303)
