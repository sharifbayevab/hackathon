from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Competition, Metric, Participant, Submission, SubmissionStatus
from app.scoring import is_higher_better


def get_active_competition(db: Session) -> Competition | None:
    stmt = select(Competition).where(Competition.is_active.is_(True)).order_by(Competition.id.desc())
    return db.scalars(stmt).first()


def deadline_passed(competition: Competition | None) -> bool:
    if competition is None or competition.deadline is None:
        return False
    deadline = competition.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= deadline


def time_to_deadline(competition: Competition) -> str | None:
    if competition.deadline is None:
        return None
    deadline = competition.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(timezone.utc)
    if delta.total_seconds() <= 0:
        return None
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes = rem // 60
    return f"{days}d {hours}h {minutes}m"


@dataclass
class LeaderboardRow:
    rank: int
    participant_id: int
    full_name: str
    group_name: str
    score: float
    submissions_count: int
    best_at: datetime


def compute_leaderboard(
    db: Session, competition: Competition, *, use_private: bool
) -> list[LeaderboardRow]:
    metric = Metric(competition.metric)
    higher = is_higher_better(metric)
    score_col = Submission.private_score if use_private else Submission.public_score
    score_order = score_col.desc() if higher else score_col.asc()

    # Per-participant: pick best score; on ties take the earliest submission.
    rn = func.row_number().over(
        partition_by=Submission.participant_id,
        order_by=[score_order, Submission.created_at.asc()],
    ).label("rn")
    cnt = func.count().over(partition_by=Submission.participant_id).label("cnt")

    inner = (
        select(
            Submission.participant_id.label("pid"),
            score_col.label("score"),
            Submission.created_at.label("best_at"),
            rn,
            cnt,
        )
        .where(
            Submission.competition_id == competition.id,
            Submission.status == SubmissionStatus.scored.value,
            score_col.isnot(None),
        )
        .subquery()
    )

    stmt = (
        select(
            Participant.id,
            Participant.full_name,
            Participant.group_name,
            inner.c.score,
            inner.c.best_at,
            inner.c.cnt,
        )
        .join(inner, inner.c.pid == Participant.id)
        .where(inner.c.rn == 1)
        .order_by(
            inner.c.score.desc() if higher else inner.c.score.asc(),
            inner.c.best_at.asc(),
        )
    )

    rows = []
    for i, (pid, name, grp, score, best_at, cnt) in enumerate(db.execute(stmt).all(), start=1):
        rows.append(
            LeaderboardRow(
                rank=i,
                participant_id=pid,
                full_name=name,
                group_name=grp,
                score=float(score),
                submissions_count=int(cnt),
                best_at=best_at,
            )
        )
    return rows


def best_submission_for_participant(
    db: Session, competition: Competition, participant_id: int, *, use_private: bool
) -> Submission | None:
    metric = Metric(competition.metric)
    higher = is_higher_better(metric)
    score_col = Submission.private_score if use_private else Submission.public_score
    order = score_col.desc() if higher else score_col.asc()
    stmt = (
        select(Submission)
        .where(
            Submission.competition_id == competition.id,
            Submission.participant_id == participant_id,
            Submission.status == SubmissionStatus.scored.value,
            score_col.isnot(None),
        )
        .order_by(order, Submission.created_at.asc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def safe_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)
    return safe or "file"
