"""multilingual descriptions

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("competition", sa.Column("description_uz", sa.Text(), nullable=False, server_default=""))
    op.add_column("competition", sa.Column("description_ru", sa.Text(), nullable=False, server_default=""))
    op.add_column("competition", sa.Column("description_en", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("competition", "description_en")
    op.drop_column("competition", "description_ru")
    op.drop_column("competition", "description_uz")
