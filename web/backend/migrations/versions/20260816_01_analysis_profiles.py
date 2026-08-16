"""Persist server-authoritative Web analysis profiles."""
from alembic import op
import sqlalchemy as sa

revision = "20260816_01"
down_revision = "20260811_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("analysis_profile", sa.String(16), nullable=False, server_default="FREE"),
    )
    op.add_column(
        "analysis_jobs",
        sa.Column("analysis_profile", sa.String(16), nullable=False, server_default="FREE"),
    )


def downgrade() -> None:
    op.drop_column("analysis_jobs", "analysis_profile")
    op.drop_column("users", "analysis_profile")
