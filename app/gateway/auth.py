import bcrypt
from fastapi import Header, HTTPException
from sqlalchemy import select

from app.infra.db import get_session
from app.models.db_models import Tenant


async def verify_api_key(x_asp_api_key: str = Header(...)):
    """
    API key must be sent in header: X-ASP-API-Key: <key>
    Gateway looks up tenant by hashed key. Returns tenant object or raises 401.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
        tenants = result.scalars().all()
        for tenant in tenants:
            if bcrypt.checkpw(
                x_asp_api_key.encode(), tenant.api_key_hash.encode()
            ):
                return tenant
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
