"""Gateway API-key authentication — ASP-FEAT-ASP-00 v1.0 §10 (I-04).

Dual-path verification during the ADR-032 Type C window (sunset date set in
the v1.0 acceptance Change Log entry PE-1):

  - New format: asp_<prefix12>_<secret32>  -> O(1) prefix lookup + 1 bcrypt.
  - Legacy:     anything else              -> O(N) scan restricted to
                                               rows with key_prefix starting
                                               'leg_' (matched with
                                               func.left(key_prefix, 4) == 'leg_',
                                               NOT LIKE — avoids '_' wildcard
                                               collision per DEFECT-021-adjacent
                                               ruling, Architect 2026-04-17).

On success: returns the Tenant row (tenant.is_active guarded).
On any failure path: raises HTTPException(401) with a deliberately opaque
`detail` so the envelope cannot be used to distinguish failure modes
(see §10 error-path information-leakage rules).

Timestamps are timezone-aware UTC per ADR-009.
"""
from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
import structlog
from fastapi import Header, HTTPException
from sqlalchemy import func, select

from app.infra.db import get_session
from app.models.db_models import Tenant, TenantApiKey
from app.utils.key_generator import is_new_format, parse_prefix

log = structlog.get_logger()

# PE-1 (OPEN) — sunset date is set in the v1.0 acceptance Change Log entry.
# Bound here as a placeholder string for structlog emission until the real
# date lands via an impl-log amendment.
_ADR032_SUNSET_PLACEHOLDER = "PE-1-pending"


def _not_expired(row: TenantApiKey) -> bool:
    """True if the row has no expiry OR expiry is still in the future."""
    if row.expires_at is None:
        return True
    return row.expires_at > datetime.now(timezone.utc)


def _unauthenticated() -> HTTPException:
    """Single opaque 401 raised from every failure mode.

    The detail string is identical across all legitimate failure paths so
    that response bodies cannot be used to distinguish: missing key, wrong
    format, prefix-not-found, bcrypt-miss, expired, revoked, inactive
    tenant. See AC-S5-06.
    """
    return HTTPException(status_code=401, detail="Invalid or missing API key")


async def verify_api_key(
    x_asp_api_key: str = Header(..., alias="X-ASP-API-Key"),
) -> Tenant:
    """Authenticate a request and return the owning Tenant.

    Raises HTTPException(401) on any failure. The RFC 7807 envelope is
    rendered by the global exception handler registered in app.main
    (app.gateway.exception_handlers.http_exception_handler).
    """
    key = x_asp_api_key

    # ---- Fast path: new format -----------------------------------------
    if is_new_format(key):
        prefix = parse_prefix(key)  # 12-char base36 string
        async with get_session() as session:
            row = (
                await session.execute(
                    select(TenantApiKey).where(
                        TenantApiKey.key_prefix == prefix,
                        TenantApiKey.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if (
                row is not None
                and _not_expired(row)
                and bcrypt.checkpw(key.encode("utf-8"), row.api_key_hash.encode("utf-8"))
            ):
                tenant = await session.get(Tenant, row.tenant_id)
                if tenant is not None and tenant.is_active:
                    log.info(
                        "auth_success",
                        path="new_format",
                        tenant_id=str(tenant.id),
                        key_prefix=prefix,
                    )
                    return tenant

        # prefix is safe to log (non-secret, per §10)
        log.warning("auth_failed", path="new_format", key_prefix=prefix)
        raise _unauthenticated()

    # ---- Slow path: legacy (sunsets at PE-1 date) -----------------------
    log.warning(
        "auth_legacy_path_used",
        key_shape="legacy",
        sunset=_ADR032_SUNSET_PLACEHOLDER,
    )
    async with get_session() as session:
        legacy_rows = (
            await session.execute(
                select(TenantApiKey).where(
                    func.left(TenantApiKey.key_prefix, 4) == "leg_",
                    TenantApiKey.is_active.is_(True),
                )
            )
        ).scalars().all()

        for row in legacy_rows:
            if not _not_expired(row):
                continue
            if bcrypt.checkpw(key.encode("utf-8"), row.api_key_hash.encode("utf-8")):
                tenant = await session.get(Tenant, row.tenant_id)
                if tenant is not None and tenant.is_active:
                    log.info(
                        "auth_success",
                        path="legacy",
                        tenant_id=str(tenant.id),
                    )
                    return tenant

    log.warning("auth_failed", path="legacy")
    raise _unauthenticated()
