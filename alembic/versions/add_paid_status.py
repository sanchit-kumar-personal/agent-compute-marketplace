"""add paid status to QuoteStatus enum

Revision ID: add_paid_status
Revises: 2f1dbf530d9b
Create Date: 2025-06-16 16:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_paid_status"
down_revision: Union[str, None] = "2f1dbf530d9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a temporary text column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.add_column(sa.Column("status_new", sa.String(50)))

    # Copy data to the temporary column
    op.execute("UPDATE quotes SET status_new = status::text")

    # Drop the old status column and enum type
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status")
    op.execute("DROP TYPE IF EXISTS quotestatus")

    # Create new enum type with 'paid' status
    op.execute(
        "CREATE TYPE quotestatus AS ENUM ('pending', 'priced', 'accepted', 'rejected', 'countered', 'paid')"
    )

    # Add new status column with updated enum
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending",
                    "priced",
                    "accepted",
                    "rejected",
                    "countered",
                    "paid",
                    name="quotestatus",
                ),
                nullable=True,
            )
        )

    # Copy data back
    op.execute("UPDATE quotes SET status = status_new::quotestatus")

    # Drop temporary column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status_new")


def downgrade() -> None:
    # Create a temporary text column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.add_column(sa.Column("status_old", sa.String(50)))

    # Copy data to the temporary column
    op.execute("UPDATE quotes SET status_old = status::text")

    # Drop the old status column and enum type
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status")
    op.execute("DROP TYPE IF EXISTS quotestatus")

    # Create old enum type without 'paid' status
    op.execute(
        "CREATE TYPE quotestatus AS ENUM ('pending', 'priced', 'accepted', 'rejected', 'countered')"
    )

    # Add old status column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending",
                    "priced",
                    "accepted",
                    "rejected",
                    "countered",
                    name="quotestatus",
                ),
                nullable=True,
            )
        )

    # Copy data back (excluding 'paid' values)
    op.execute(
        "UPDATE quotes SET status = CASE WHEN status_old != 'paid' THEN status_old::quotestatus ELSE NULL END"
    )

    # Drop temporary column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status_old")
