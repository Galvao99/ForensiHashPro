"""Add persistent operational analysis jobs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260809_01"
down_revision = "20260808_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("retention_mode", sa.String(24), nullable=False),
        sa.Column("staging_path", sa.Text(), nullable=True),
        sa.Column("staging_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("current_stage", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(400), nullable=True),
        sa.Column("result_analysis_id", sa.String(36), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_token", sa.String(36), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_jobs_user_id", "analysis_jobs", ["user_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_result_analysis_id", "analysis_jobs", ["result_analysis_id"])
    op.create_index("ix_analysis_jobs_created_at", "analysis_jobs", ["created_at"])
    op.create_index("ix_analysis_jobs_heartbeat_at", "analysis_jobs", ["heartbeat_at"])


def downgrade() -> None:
    op.drop_table("analysis_jobs")
