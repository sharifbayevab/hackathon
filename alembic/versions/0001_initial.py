"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competition",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("metric", sa.String(32), nullable=False, server_default="accuracy"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_column", sa.String(64), nullable=False, server_default="id"),
        sa.Column("answer_column", sa.String(64), nullable=False, server_default="answer"),
        sa.Column("train_path", sa.String(512), nullable=True),
        sa.Column("sample_submission_path", sa.String(512), nullable=True),
        sa.Column("groundtruth_path", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "participant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("full_name_norm", sa.String(255), nullable=False),
        sa.Column("group_name_norm", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("full_name_norm", "group_name_norm", name="uq_participant_identity"),
    )
    op.create_index("ix_participant_full_name_norm", "participant", ["full_name_norm"])
    op.create_index("ix_participant_group_name_norm", "participant", ["group_name_norm"])

    op.create_table(
        "submission",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competition.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("public_score", sa.Float(), nullable=True),
        sa.Column("private_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="scored"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submission_competition_id", "submission", ["competition_id"])
    op.create_index("ix_submission_participant_id", "submission", ["participant_id"])
    op.create_index("ix_submission_created_at", "submission", ["created_at"])

    op.create_table(
        "admin_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_user")
    op.drop_index("ix_submission_created_at", table_name="submission")
    op.drop_index("ix_submission_participant_id", table_name="submission")
    op.drop_index("ix_submission_competition_id", table_name="submission")
    op.drop_table("submission")
    op.drop_index("ix_participant_group_name_norm", table_name="participant")
    op.drop_index("ix_participant_full_name_norm", table_name="participant")
    op.drop_table("participant")
    op.drop_table("competition")
