"""Retain observed versions, owner policies, and deletion work.

Revision ID: a22b8c30d567
Revises: f13a7b20c456
"""
import hashlib
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a22b8c30d567"
down_revision = "f13a7b20c456"
branch_labels = depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("policy_revision", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_artifacts", sa.Column("blocked_at", sa.DateTime(timezone=True)))
    for column in [
        sa.Column("source_scope", sa.String(255), nullable=False, server_default="default"),
        sa.Column("current_version_id", sa.Integer()), sa.Column("latest_source_updated_at", sa.DateTime(timezone=True)), sa.Column("annotation", sa.Text()),
        sa.Column("source_state", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("source_state_observed_at", sa.DateTime(timezone=True)),
        sa.Column("external_ai_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default="false"),
    ]:
        op.add_column("entries", column)
    op.create_table("source_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("collection_enabled", sa.Boolean(), nullable=False),
        sa.Column("external_ai_allowed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_id", "provider", "scope"))
    op.create_table("entry_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("content", sa.Text()),
        sa.Column("entry_type", sa.String(50), nullable=False), sa.Column("event_at", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)), sa.Column("locator", sa.Text()),
        sa.Column("parser_version", sa.String(100), nullable=False), sa.Column("completeness", sa.String(20), nullable=False),
        sa.Column("material_kind", sa.String(30), nullable=False), sa.Column("payload", JSONB),
        sa.Column("import_artifact_id", sa.Integer(), sa.ForeignKey("import_artifacts.id", ondelete="SET NULL")),
        sa.UniqueConstraint("entry_id", "number"))
    op.create_table("entry_materials",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("import_artifacts.id", ondelete="CASCADE"), primary_key=True))
    op.execute("INSERT INTO entry_materials SELECT id,import_artifact_id FROM entries WHERE import_artifact_id IS NOT NULL")
    op.create_index("ix_entry_versions_entry_id", "entry_versions", ["entry_id"])
    op.create_table("entry_suppressions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("reimport_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "provider", "external_id"))
    op.create_table("object_purges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("s3_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("import_artifacts.id", ondelete="SET NULL")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("last_error", sa.String(100)))
    op.create_foreign_key("fk_entries_current_version", "entries", "entry_versions", ["current_version_id"], ["id"], ondelete="SET NULL")
    bind = op.get_bind()
    # Stream old rows: preserve one known observation, never infer source modification time.
    rows = bind.execute(sa.text("SELECT * FROM entries ORDER BY id").execution_options(stream_results=True)).mappings()
    for row in rows:
        if row["provider"] == "markdown" and row["external_id"] is None:
            identity = "sha256:" + hashlib.sha256((row["content"] or "").encode("utf-8")).hexdigest()
            collision = bind.execute(sa.text("SELECT id FROM entries WHERE user_id=:owner AND provider='markdown' AND external_id=:identity"),
                                     {"owner": row["user_id"], "identity": identity}).scalar()
            # Preserve old duplicate rows independently; only the first represents future byte-identical uploads.
            bind.execute(sa.text("UPDATE entries SET external_id=:identity WHERE id=:id"),
                         {"id": row["id"], "identity": f"legacy:{row['id']}" if collision else identity})
        values = dict(type=row["type"], title=row["title"], content=row["content"],
                      event_at=row["event_at"].isoformat() if row["event_at"] else None)
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        version_id = bind.execute(sa.text("""INSERT INTO entry_versions
            (entry_id, number, content_hash, title, content, entry_type, event_at, observed_at,
             parser_version, completeness, material_kind, import_artifact_id)
            VALUES (:id, 1, :hash, :title, :content, :type, :event_at, :updated_at,
                    'initial-observed-v1', 'unknown', 'legacy', :import_artifact_id) RETURNING id"""),
            {**row, "hash": digest}).scalar_one()
        bind.execute(sa.text("UPDATE entries SET current_version_id=:version WHERE id=:id"),
                     {"version": version_id, "id": row["id"]})
    op.execute("""INSERT INTO source_policies (user_id,provider,scope,collection_enabled,external_ai_allowed)
                  SELECT DISTINCT user_id, COALESCE(provider,'unknown'),'default',true,false FROM entries""")


def downgrade() -> None:
    op.drop_constraint("fk_entries_current_version", "entries", type_="foreignkey")
    for table in ("object_purges", "entry_suppressions", "entry_materials", "entry_versions", "source_policies"):
        op.drop_table(table)
    for name in ("source_scope", "current_version_id", "latest_source_updated_at", "annotation", "source_state", "source_state_observed_at",
                 "external_ai_allowed", "review_required"):
        op.drop_column("entries", name)
    op.drop_column("import_artifacts", "blocked_at")
    op.drop_column("users", "policy_revision")
