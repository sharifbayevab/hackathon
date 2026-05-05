from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    LANG_COOKIE,
    clear_participant_cookie,
    get_participant_id,
    normalize_identity,
    set_participant_cookie,
)
from app.config import settings
from app.db import get_db
from app.i18n import SUPPORTED, normalize, translator
from app.models import Competition, Metric, Participant, Submission, SubmissionStatus
from app.scoring import ScoringError, load_groundtruth, score_submission
from app.services import (
    compute_leaderboard,
    deadline_passed,
    get_active_competition,
    safe_filename,
    time_to_deadline,
)
from app.templating import get_lang, render

router = APIRouter()


def _current_participant(request: Request, db: Session) -> Participant | None:
    pid = get_participant_id(request)
    if pid is None:
        return None
    return db.get(Participant, pid)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    participant = _current_participant(request, db)
    if participant:
        return RedirectResponse("/task", status_code=303)
    return render(request, "index.html", {"participant": None})


@router.post("/login")
def login(
    request: Request,
    full_name: str = Form(...),
    group_name: str = Form(...),
    db: Session = Depends(get_db),
):
    t = translator(get_lang(request))
    full_name = full_name.strip()
    group_name = group_name.strip()
    if not full_name or not group_name:
        return render(
            request,
            "index.html",
            {"participant": None, "error": t("error_required_fields")},
        )

    name_norm = normalize_identity(full_name)
    group_norm = normalize_identity(group_name)
    stmt = select(Participant).where(
        Participant.full_name_norm == name_norm,
        Participant.group_name_norm == group_norm,
    )
    participant = db.scalars(stmt).first()
    if participant is None:
        participant = Participant(
            full_name=full_name,
            group_name=group_name,
            full_name_norm=name_norm,
            group_name_norm=group_norm,
        )
        db.add(participant)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            participant = db.scalars(stmt).first()
        db.refresh(participant)

    response = RedirectResponse("/task", status_code=303)
    set_participant_cookie(response, participant.id)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    clear_participant_cookie(response)
    return response


@router.get("/lang/{lang}")
def set_language(lang: str, request: Request):
    target = normalize(lang)
    referer = request.headers.get("referer") or "/"
    response = RedirectResponse(referer, status_code=303)
    response.set_cookie(LANG_COOKIE, target, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@router.get("/task")
def task(request: Request, db: Session = Depends(get_db)):
    participant = _current_participant(request, db)
    if participant is None:
        return RedirectResponse("/", status_code=303)

    competition = get_active_competition(db)
    submissions: list[Submission] = []
    if competition:
        stmt = (
            select(Submission)
            .where(
                Submission.competition_id == competition.id,
                Submission.participant_id == participant.id,
            )
            .order_by(Submission.created_at.desc())
            .limit(50)
        )
        submissions = list(db.scalars(stmt).all())

    return render(
        request,
        "task.html",
        {
            "participant": participant,
            "competition": competition,
            "submissions": submissions,
            "deadline_passed": deadline_passed(competition),
            "time_left": time_to_deadline(competition) if competition else None,
            "flash": request.query_params.get("flash"),
            "flash_score": request.query_params.get("score"),
            "flash_error": request.query_params.get("error"),
        },
    )


@router.post("/submit")
async def submit(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    participant = _current_participant(request, db)
    if participant is None:
        return RedirectResponse("/", status_code=303)
    t = translator(get_lang(request))

    competition = get_active_competition(db)
    if competition is None:
        return RedirectResponse(f"/task?error={quote_plus(t('error_no_active_task'))}", status_code=303)
    if not competition.groundtruth_path:
        return RedirectResponse(f"/task?error={quote_plus(t('error_no_groundtruth'))}", status_code=303)
    if deadline_passed(competition):
        return RedirectResponse(f"/task?error={quote_plus(t('error_deadline_passed'))}", status_code=303)

    settings.submissions_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{participant.id}_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}.csv"
    dst = settings.submissions_dir / fname
    with dst.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    submission = Submission(
        competition_id=competition.id,
        participant_id=participant.id,
        file_path=str(dst),
        status=SubmissionStatus.scored.value,
    )

    try:
        gt = load_groundtruth(
            Path(competition.groundtruth_path), competition.id_column, competition.answer_column
        )
        result = score_submission(
            dst, gt, Metric(competition.metric), competition.id_column, competition.answer_column
        )
        submission.public_score = result.public
        submission.private_score = result.private
        submission.status = SubmissionStatus.scored.value
        submission.error_message = None
    except ScoringError as e:
        submission.status = SubmissionStatus.failed.value
        submission.error_message = str(e)

    db.add(submission)
    db.commit()
    db.refresh(submission)

    if submission.status == SubmissionStatus.scored.value:
        score_str = f"{submission.public_score:.5f}"
        return RedirectResponse(f"/task?flash=ok&score={score_str}", status_code=303)
    else:
        return RedirectResponse(
            f"/task?error={quote_plus(submission.error_message or 'unknown')}", status_code=303
        )


@router.get("/leaderboard")
def leaderboard(request: Request, db: Session = Depends(get_db)):
    competition = get_active_competition(db)
    rows = []
    use_private = False
    if competition:
        use_private = deadline_passed(competition)
        rows = compute_leaderboard(db, competition, use_private=use_private)
    return render(
        request,
        "leaderboard.html",
        {
            "participant": _current_participant(request, db),
            "competition": competition,
            "rows": rows,
            "use_private": use_private,
        },
    )


@router.get("/download/train")
def download_train(db: Session = Depends(get_db)):
    competition = get_active_competition(db)
    if not competition or not competition.train_path:
        raise HTTPException(404)
    p = Path(competition.train_path)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, filename=safe_filename(f"train_{competition.id}.csv"))


@router.get("/download/sample")
def download_sample(db: Session = Depends(get_db)):
    competition = get_active_competition(db)
    if not competition or not competition.sample_submission_path:
        raise HTTPException(404)
    p = Path(competition.sample_submission_path)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, filename=safe_filename(f"sample_submission_{competition.id}.csv"))
