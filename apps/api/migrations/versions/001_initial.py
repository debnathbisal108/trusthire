"""Initial schema — all tables.

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), server_default="starter"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_org_slug", "organizations", ["slug"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("google_id", sa.String(255), nullable=True, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="recruiter"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_users_email", "users", ["email"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_users_org", "users", ["organization_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # candidates
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("parsed_data", postgresql.JSONB, nullable=True),
        sa.Column("linkedin_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False),
        sa.Column("risk_score", sa.SmallInteger, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_candidates_org", "candidates", ["organization_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_candidates_status", "candidates", ["status"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("doc_type", sa.String(50), server_default="resume"),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("scan_status", sa.String(30), server_default="pending"),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_docs_candidate", "documents", ["candidate_id"])

    # verification_requests
    op.create_table(
        "verification_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False),
        sa.Column("config", postgresql.JSONB, server_default="{}"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_verif_candidate", "verification_requests", ["candidate_id"])
    op.create_index("idx_verif_status", "verification_requests", ["status"])

    # consent_records
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("granted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("consent_text", sa.Text, nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_consent_candidate", "consent_records", ["candidate_id", "consent_type"])

    # employment_records
    op.create_table(
        "employment_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_name", sa.String(500), nullable=False),
        sa.Column("job_title", sa.String(500), nullable=True),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("responsibilities", sa.Text, nullable=True),
        sa.Column("company_domain", sa.String(255), nullable=True),
        sa.Column("hr_email", sa.String(255), nullable=True),
        sa.Column("hr_phone", sa.String(100), nullable=True),
        sa.Column("verification_status", sa.String(50), server_default="pending"),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(50), nullable=True),
        sa.Column("verifier_name", sa.String(255), nullable=True),
        sa.Column("confidence_score", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_suspicious", sa.Boolean, server_default="false"),
        sa.Column("fraud_reasons", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_employment_candidate", "employment_records", ["candidate_id"])

    # education_records
    op.create_table(
        "education_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_name", sa.String(500), nullable=False),
        sa.Column("degree", sa.String(255), nullable=True),
        sa.Column("field_of_study", sa.String(255), nullable=True),
        sa.Column("graduation_year", sa.SmallInteger, nullable=True),
        sa.Column("gpa", sa.Float, nullable=True),
        sa.Column("institution_country", sa.String(100), nullable=True),
        sa.Column("accreditation_body", sa.String(255), nullable=True),
        sa.Column("verification_status", sa.String(50), server_default="pending"),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_suspicious", sa.Boolean, server_default="false"),
        sa.Column("fraud_reasons", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_education_candidate", "education_records", ["candidate_id"])

    # email_logs
    op.create_table(
        "email_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("verification_request_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("verification_requests.id"), nullable=True),
        sa.Column("employment_record_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employment_records.id"), nullable=True),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("from_address", sa.String(255), nullable=False),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("replied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reply_text", sa.Text, nullable=True),
        sa.Column("reply_verified", sa.Boolean, nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("followup_count", sa.Integer, server_default="0"),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_email_verif", "email_logs", ["verification_request_id"])

    # fraud_flags
    op.create_table(
        "fraud_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flag_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence", postgresql.JSONB, server_default="{}"),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("requires_review", sa.Boolean, server_default="true"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("review_outcome", sa.String(50), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_fraud_candidate", "fraud_flags", ["candidate_id"])
    op.create_index("idx_fraud_severity", "fraud_flags", ["severity"],
                    postgresql_where=sa.text("reviewed_at IS NULL"))

    # risk_scores
    op.create_table(
        "risk_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verification_request_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("verification_requests.id"), nullable=True),
        sa.Column("overall_score", sa.SmallInteger, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("employment_score", sa.SmallInteger, nullable=True),
        sa.Column("education_score", sa.SmallInteger, nullable=True),
        sa.Column("fraud_score", sa.SmallInteger, nullable=True),
        sa.Column("public_record_score", sa.SmallInteger, nullable=True),
        sa.Column("score_breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("calculated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("model_version", sa.String(50), server_default="1.0"),
    )
    op.create_index("idx_risk_candidate", "risk_scores", ["candidate_id"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_org", "audit_logs", ["organization_id", "created_at"])
    op.create_index("idx_audit_candidate", "audit_logs", ["candidate_id", "created_at"])

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("data", postgresql.JSONB, server_default="{}"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_notif_user", "notifications", ["user_id"],
                    postgresql_where=sa.text("is_read = false"))


def downgrade() -> None:
    for table in [
        "notifications", "audit_logs", "risk_scores", "fraud_flags",
        "email_logs", "education_records", "employment_records",
        "consent_records", "verification_requests", "documents", "candidates",
        "users", "organizations",
    ]:
        op.drop_table(table)
