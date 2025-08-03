#!/usr/bin/env python3
"""
Cleanup script to release expired reservations and free compute resources.
Can be run as a cron job or manually.
"""

import sys
import os
from datetime import UTC, datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from db.models import ComputeResource, Reservation  # noqa: E402
from core.dependencies import get_settings  # noqa: E402
import structlog  # noqa: E402

log = structlog.get_logger(__name__)


def cleanup_expired_reservations():
    """Clean up expired reservations and free compute resources."""
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()

    try:
        # Find expired reservations
        now = datetime.now(UTC)
        expired_reservations = (
            db.query(Reservation)
            .filter(Reservation.expires_at <= now, Reservation.status == "active")
            .all()
        )

        if not expired_reservations:
            print("✅ No expired reservations found")
            return

        for reservation in expired_reservations:
            # Free up reserved resources
            freed_resources = (
                db.query(ComputeResource)
                .filter(
                    ComputeResource.type == reservation.resource_type.upper(),
                    ComputeResource.status == "reserved",
                )
                .limit(reservation.quantity)
                .all()
            )

            for resource in freed_resources:
                resource.status = "available"

            # Mark reservation as expired
            reservation.status = "expired"

            log.info(
                "reservation.expired",
                reservation_id=reservation.id,
                quote_id=reservation.quote_id,
                resource_type=reservation.resource_type,
                quantity=len(freed_resources),
            )

        db.commit()
        print(f"✅ Cleaned up {len(expired_reservations)} expired reservations")
        print(
            f"   - Freed {sum(r.quantity for r in expired_reservations)} resource units"
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Error cleaning up reservations: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_expired_reservations()
