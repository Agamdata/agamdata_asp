"""
Create a tenant and generate an API key.

Usage:
    python scripts/create_tenant.py
    python scripts/create_tenant.py --code myapp --name "My App" --quota 100
"""
import argparse
import secrets
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import re

from app.config import settings
from app.models.db_models import Tenant


def create_tenant(tenant_code: str, name: str, quota_usd: float) -> None:
    # Generate a secure random API key
    raw_api_key = f"asp-{secrets.token_urlsafe(32)}"

    # Bcrypt hash the key for storage
    api_key_hash = bcrypt.hashpw(raw_api_key.encode(), bcrypt.gensalt(rounds=12)).decode()

    # Use sync DB URL (alembic-style)
    sync_url = re.sub(r"postgresql\+asyncpg", "postgresql", settings.DATABASE_URL)
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        # Check if tenant already exists
        existing = session.query(Tenant).filter_by(tenant_code=tenant_code).first()
        if existing:
            print(f"\n⚠️  Tenant '{tenant_code}' already exists.")
            print(f"   ID       : {existing.id}")
            print(f"   Name     : {existing.name}")
            print(f"   Active   : {existing.is_active}")
            print("\n   To reset the API key, delete the tenant and re-run this script.")
            return

        tenant = Tenant(
            tenant_code=tenant_code,
            name=name,
            api_key_hash=api_key_hash,
            monthly_quota_usd=quota_usd,
            is_active=True,
        )
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

        print("\n✅  Tenant created successfully!")
        print("=" * 55)
        print(f"  Tenant Code : {tenant.tenant_code}")
        print(f"  Name        : {tenant.name}")
        print(f"  Tenant ID   : {tenant.id}")
        print(f"  Quota USD   : ${quota_usd:.2f} / month")
        print("=" * 55)
        print(f"  API Key     : {raw_api_key}")
        print("=" * 55)
        print("\n⚠️  SAVE THIS API KEY — it will NOT be shown again!\n")
        print("  Use it in requests as:")
        print(f"  X-ASP-Api-Key: {raw_api_key}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an ASP tenant")
    parser.add_argument("--code", default="default", help="Tenant code (unique short identifier)")
    parser.add_argument("--name", default="Default Tenant", help="Tenant display name")
    parser.add_argument("--quota", type=float, default=50.0, help="Monthly quota in USD")
    args = parser.parse_args()

    create_tenant(
        tenant_code=args.code,
        name=args.name,
        quota_usd=args.quota,
    )
