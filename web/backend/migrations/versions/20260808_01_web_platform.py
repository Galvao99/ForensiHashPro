"""Create users, privacy preferences, consents and analyses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("role", sa.String(16), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("session_version", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("privacy_preferences", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True), sa.Column("retention_mode", sa.String(24), nullable=False), sa.Column("retain_analysis_results", sa.Boolean(), nullable=False), sa.Column("retain_original_files", sa.Boolean(), nullable=False), sa.Column("allow_external_services", sa.Boolean(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("consents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("document_type", sa.String(32), nullable=False), sa.Column("document_version", sa.String(32), nullable=False), sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("user_id", "document_type", "document_version"))
    op.create_index("ix_consents_user_id", "consents", ["user_id"])
    op.create_table("analyses", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("filename", sa.String(255), nullable=False), sa.Column("detected_type", sa.String(120)), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("retention_mode", sa.String(24), nullable=False), sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])
    op.create_index("ix_analyses_sha256", "analyses", ["sha256"])
    op.create_index("ix_analyses_status", "analyses", ["status"])


def downgrade() -> None:
    op.drop_table("analyses")
    op.drop_table("consents")
    op.drop_table("privacy_preferences")
    op.drop_table("users")
