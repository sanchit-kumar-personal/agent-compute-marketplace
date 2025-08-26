#!/usr/bin/env python3
"""
Database initialization script that runs migrations and seeds initial data.
This runs automatically when the API container starts up.
"""

import sys
import os
import time
import subprocess
from datetime import UTC, datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from db.models import ComputeResource, Quote, QuoteStatus  # noqa: E402
from core.dependencies import get_settings, init_settings  # noqa: E402
from agents.negotiation_engine import NegotiationEngine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def wait_for_db(max_attempts=30, delay=2):
    """Wait for database to be ready."""
    settings = get_settings()

    for attempt in range(max_attempts):
        try:
            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"✅ Database ready after {attempt + 1} attempts")
            engine.dispose()
            return True
        except OperationalError:
            print(f"⏳ Database not ready, attempt {attempt + 1}/{max_attempts}...")
            time.sleep(delay)
        except Exception as e:
            print(f"❌ Unexpected error connecting to database: {e}")
            time.sleep(delay)

    print(f"❌ Database not ready after {max_attempts} attempts")
    return False


def run_migrations():
    """Run Alembic migrations."""
    try:
        print("🔄 Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✅ Migrations completed successfully")
            return True
        else:
            # If migrations failed due to duplicate tables (already applied), treat as success
            if "DuplicateTable" in result.stderr or "already exists" in result.stderr:
                print("⚠️  Migrations already applied (duplicate tables), continuing")
                return True
            print(f"❌ Migration failed: {result.stderr}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        return False


def seed_initial_data():
    """Seed initial compute resources if table is empty."""
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()

        # Check if we already have data
        existing_count = db.query(ComputeResource).count()
        if existing_count > 0:
            print(f"✅ Database already has {existing_count} compute resources")
            db.close()
            return True

        print("🌱 Seeding initial compute resources...")

        # GPU resources (100 units total)
        for i in range(100):
            gpu = ComputeResource(
                type="GPU",
                specs='{"gpu_model": "NVIDIA A100", "memory_gb": 80, "cpu_cores": 8, "storage_gb": 1000}',
                price_per_hour=2.5,
                status="available",
                created_at=datetime.now(UTC),
            )
            db.add(gpu)

        # CPU resources (500 units total)
        for i in range(500):
            cpu = ComputeResource(
                type="CPU",
                specs='{"cpu_cores": 16, "memory_gb": 64, "storage_gb": 500}',
                price_per_hour=0.8,
                status="available",
                created_at=datetime.now(UTC),
            )
            db.add(cpu)

        # TPU resources (50 units total)
        for i in range(50):
            tpu = ComputeResource(
                type="TPU",
                specs='{"tpu_model": "TPU v4", "memory_gb": 128, "cpu_cores": 32, "storage_gb": 2000}',
                price_per_hour=6.0,
                status="available",
                created_at=datetime.now(UTC),
            )
            db.add(tpu)

        db.commit()
        print("✅ Successfully seeded compute resources")
        print("   - 100 GPU units")
        print("   - 500 CPU units")
        print("   - 50 TPU units")

        # Optional: seed demo quotes
        if os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}:
            print("🌱 Seeding demo quotes...")
            demo_quotes = [
                Quote(
                    buyer_id="demo_buyer_1",
                    resource_type="GPU",
                    duration_hours=4,
                    buyer_max_price=15.0,
                    price=0.0,
                    status=QuoteStatus.pending,
                ),
                Quote(
                    buyer_id="demo_buyer_2",
                    resource_type="CPU",
                    duration_hours=8,
                    buyer_max_price=8.0,
                    price=0.0,
                    status=QuoteStatus.pending,
                ),
            ]
            db.add_all(demo_quotes)
            db.commit()

            print("✅ Demo quotes seeded")

        db.close()
        engine.dispose()
        return True

    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        if "db" in locals():
            db.rollback()
            db.close()
        return False


def init_database():
    """Initialize database with migrations and seed data."""
    print("🚀 Initializing database...")

    # Ensure settings are initialized so get_settings() works
    init_settings()

    # Wait for database to be ready
    if not wait_for_db():
        print("❌ Database initialization failed - database not ready")
        sys.exit(1)

    # Run migrations
    if not run_migrations():
        print("❌ Database initialization failed - migration error")
        sys.exit(1)

    # Seed initial data
    if not seed_initial_data():
        print("❌ Database initialization failed - seeding error")
        sys.exit(1)

    # Optional: run a brief demo negotiation to showcase end-to-end
    try:
        if os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}:
            print("🤝 Running demo negotiation…")
            settings = get_settings()
            engine = create_engine(settings.DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db: Session = SessionLocal()

            # Pick the most recent pending quote
            q = (
                db.query(Quote)
                .filter(Quote.status == QuoteStatus.pending)
                .order_by(Quote.id.desc())
                .first()
            )
            if q:
                # Use the negotiation engine with a sync adapter path
                from starlette.concurrency import run_in_threadpool

                class AsyncAdapter:
                    def __init__(self, inner):
                        self._inner = inner

                    def add(self, obj):
                        return self._inner.add(obj)

                    async def commit(self):
                        await run_in_threadpool(self._inner.commit)

                    async def refresh(self, obj):
                        await run_in_threadpool(lambda: self._inner.refresh(obj))

                    async def execute(self, stmt):
                        return await run_in_threadpool(
                            lambda: self._inner.execute(stmt)
                        )

                    @property
                    def sync_session(self):
                        return self._inner

                adapter = AsyncAdapter(db)
                engine_neg = NegotiationEngine()
                # Initial pricing
                import asyncio

                asyncio.run(engine_neg.run_loop(adapter, q.id))
            db.close()
            engine.dispose()
            print("✅ Demo negotiation completed")
    except Exception as e:
        print(f"⚠️  Demo negotiation skipped: {e}")

    print("🎉 Database initialization completed successfully!")


if __name__ == "__main__":
    init_database()
