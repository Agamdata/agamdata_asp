"""Gateway v1.0 — tenant_api_keys junction + caller_feature on cost_events

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-17

Locks ADR-032 code mechanics (multi-key rotation, 90-day Type C window).
Governs F-01-10 caller_feature capture in cost_events.

Per ASP-FEAT-ASP-00 v1.0 §5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    # Step sequence — ORDER IS CRITICAL for rollback safety:
    # 1. CREATE tenant_api_keys (new table, no dependency yet)
    # 2. INSERT legacy rows (backfill before DROP — data preserved)
    # 3. ALTER cost_events ADD caller_feature (independent, safe)
    # 4. DROP tenants.api_key_hash (only after backfill confirmed)
    # If migration fails at step 4: tenants.api_key_hash still exists,
    # tenant_api_keys has legacy rows, no data loss.

    # ---- Step 1: CREATE tenant_api_keys -----------------------------------
    op.create_table(
        "tenant_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("TRUE")),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_tenant_api_keys_prefix",
        "tenant_api_keys",
        ["key_prefix"],
        unique=True,
    )
    op.create_index(
        "ix_tenant_api_keys_tenant",
        "tenant_api_keys",
        ["tenant_id", "is_active"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_tenant_api_keys_revocation_consistency",
        "tenant_api_keys",
        "(revoked_at IS NULL AND is_active = TRUE) "
        "OR (revoked_at IS NOT NULL AND is_active = FALSE)",
    )
    op.create_check_constraint(
        "ck_tenant_api_keys_expiry_order",
        "tenant_api_keys",
        "expires_at IS NULL OR expires_at > issued_at",
    )

    # ---- Step 2: INSERT legacy rows (backfill) ----------------------------
    # Legacy key_prefix format: 'leg_' || substr(tenant_id::text, 1, 8)
    # Always 12 chars. Matched in auth.py via func.left(key_prefix, 4) == 'leg_'
    # (NOT via LIKE — avoids '_' wildcard collision with new-format prefixes).
    op.execute("""
        INSERT INTO tenant_api_keys
            (tenant_id, key_prefix, api_key_hash, label,
             is_active, issued_at, created_at, updated_at)
        SELECT
            id,
            'leg_' || substr(id::text, 1, 8),
            api_key_hash,
            'legacy',
            is_active,
            created_at,
            created_at,
            now()
        FROM tenants
        WHERE api_key_hash IS NOT NULL;
    """)

    # ---- Step 3: ADD cost_events.caller_feature ---------------------------
    # F-01-10 governance — per §7 / AC-S6-02..05.
    # NULL means pre-feature row or non-PAP caller (§5 governed semantics).
    op.add_column(
        "cost_events",
        sa.Column("caller_feature", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_cost_events_caller_feature",
        "cost_events",
        ["caller_feature"],
        unique=False,
    )

    # ---- Step 4: DROP tenants.api_key_hash (LAST) -------------------------
    # Authoritative source of truth now in tenant_api_keys.
    op.drop_column("tenants", "api_key_hash")


def downgrade():
    # Reverse order — exact opposite of upgrade():
    #   1. ADD api_key_hash back to tenants (nullable initially)
    #   2. UPDATE tenants.api_key_hash from tenant_api_keys legacy rows
    #   3. ALTER api_key_hash to NOT NULL (after backfill confirmed)
    #   4. DROP cost_events.caller_feature
    #   5. DROP tenant_api_keys (after data recovered)

    # ---- Step 1: re-add api_key_hash on tenants (nullable) ---------------
    op.add_column(
        "tenants",
        sa.Column("api_key_hash", sa.String(255), nullable=True),
    )

    # ---- Step 2: restore api_key_hash from legacy rows -------------------
    # Pick the oldest legacy row per tenant (DISTINCT ON + ORDER BY issued_at ASC).
    op.execute("""
        UPDATE tenants t
        SET api_key_hash = sub.api_key_hash
        FROM (
            SELECT DISTINCT ON (tenant_id) tenant_id, api_key_hash
            FROM tenant_api_keys
            WHERE left(key_prefix, 4) = 'leg_'
              AND is_active = TRUE
            ORDER BY tenant_id, issued_at ASC
        ) sub
        WHERE t.id = sub.tenant_id;
    """)

    # ---- Step 3: enforce NOT NULL (after backfill confirmed) -------------
    # Defensive: only tenants that had a legacy row now have api_key_hash set.
    # If any active tenant lacks a legacy row, this ALTER will fail — caller
    # must investigate rather than lose the NOT NULL invariant silently.
    op.alter_column("tenants", "api_key_hash", nullable=False)

    # ---- Step 4: drop cost_events.caller_feature -------------------------
    op.drop_index("ix_cost_events_caller_feature", table_name="cost_events")
    op.drop_column("cost_events", "caller_feature")

    # ---- Step 5: drop tenant_api_keys (data now restored on tenants) -----
    op.drop_constraint("ck_tenant_api_keys_expiry_order", "tenant_api_keys")
    op.drop_constraint("ck_tenant_api_keys_revocation_consistency", "tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_tenant", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_prefix", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")
