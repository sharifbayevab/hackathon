from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Metric(str, Enum):
    accuracy = "accuracy"
    f1_macro = "f1_macro"
    f1_binary = "f1_binary"
    roc_auc = "roc_auc"
    log_loss = "log_loss"
    mae = "mae"
    rmse = "rmse"
    r2 = "r2"


HIGHER_IS_BETTER = {
    Metric.accuracy: True,
    Metric.f1_macro: True,
    Metric.f1_binary: True,
    Metric.roc_auc: True,
    Metric.log_loss: False,
    Metric.mae: False,
    Metric.rmse: False,
    Metric.r2: True,
}


class SubmissionStatus(str, Enum):
    scored = "scored"
    failed = "failed"


class Competition(Base):
    __tablename__ = "competition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_uz: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_ru: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metric: Mapped[str] = mapped_column(String(32), nullable=False, default=Metric.accuracy.value)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_column: Mapped[str] = mapped_column(String(64), nullable=False, default="id")
    answer_column: Mapped[str] = mapped_column(String(64), nullable=False, default="answer")
    train_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sample_submission_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    groundtruth_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    submissions: Mapped[list["Submission"]] = relationship(back_populates="competition")


class Participant(Base):
    __tablename__ = "participant"
    __table_args__ = (UniqueConstraint("full_name_norm", "group_name_norm", name="uq_participant_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_norm: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    group_name_norm: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submissions: Mapped[list["Submission"]] = relationship(back_populates="participant")


class Submission(Base):
    __tablename__ = "submission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competition.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participant.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    public_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    private_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SubmissionStatus.scored.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    competition: Mapped[Competition] = relationship(back_populates="submissions")
    participant: Mapped[Participant] = relationship(back_populates="submissions")


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
