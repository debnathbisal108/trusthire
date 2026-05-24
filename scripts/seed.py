"""
TrustHire AI — Database seed script.
Creates a demo organization, admin user, and sample candidate.
Run: python scripts/seed.py
"""

import asyncio
import uuid
import sys
import os

# Add the api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from database import AsyncSessionLocal, engine, Base
from models import Organization, User, Candidate
from security import generate_slug


async def seed():
    print("🌱 Seeding TrustHire AI database...")

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✅ Tables created")

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        from sqlalchemy import select
        existing = await db.scalar(select(Organization).limit(1))
        if existing:
            print("  ⏭️  Database already seeded — skipping")
            return

        # Create demo organization
        org = Organization(
            id=uuid.uuid4(),
            name="Acme Recruiting",
            slug=generate_slug("Acme Recruiting"),
            plan="starter",
            settings={},
        )
        db.add(org)
        await db.flush()

        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email="admin@acmerecruiting.com",
            full_name="Demo Admin",
            role="org_admin",
            is_active=True,
        )
        db.add(admin)

        # Create recruiter user
        recruiter = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email="recruiter@acmerecruiting.com",
            full_name="Demo Recruiter",
            role="recruiter",
            is_active=True,
        )
        db.add(recruiter)
        await db.flush()

        # Create sample candidate
        sample = Candidate(
            id=uuid.uuid4(),
            organization_id=org.id,
            created_by=recruiter.id,
            full_name="Jane Smith",
            status="pending",
        )
        db.add(sample)

        await db.commit()

    print("  ✅ Demo organization:  Acme Recruiting")
    print("  ✅ Admin user:         admin@acmerecruiting.com")
    print("  ✅ Recruiter user:     recruiter@acmerecruiting.com")
    print("  ✅ Sample candidate:   Jane Smith")
    print("")
    print("  ℹ️  Login with Google OAuth — the first sign-in automatically")
    print("     creates a new organization for your Google account.")
    print("")


if __name__ == "__main__":
    asyncio.run(seed())
