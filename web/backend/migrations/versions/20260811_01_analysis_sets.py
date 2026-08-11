"""Add logical analysis sets and correlation results."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260811_01"
down_revision = "20260809_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("job_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_sets_user_id", "analysis_sets", ["user_id"])
    op.create_index("ix_analysis_sets_state", "analysis_sets", ["state"])
    op.create_index("ix_analysis_sets_expires_at", "analysis_sets", ["expires_at"])


def downgrade() -> None:
    op.drop_table("analysis_sets")
