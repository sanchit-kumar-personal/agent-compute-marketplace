"""add buyer_max_price and new enum values

Revision ID: 2c_buyer_max_price
Revises: 07086b849fda
Create Date: 2025-06-10 15:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c_buyer_max_price"
down_revision: str | None = "07086b849fda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create a temporary text column
    with op.batch_alter_table("quotes") as batch_op:
        # Add buyer_max_price column first
        batch_op.add_column(
            sa.Column(
                "buyer_max_price",
                sa.Numeric(precision=10, scale=2),
                nullable=False,
                server_default="0.0",
            )
        )

        # Add temporary column
        batch_op.add_column(sa.Column("status_new", sa.String(50)))

    # Copy data to the temporary column if status exists
    op.execute("UPDATE quotes SET status_new = status::text")

    # Create new enum type first
    op.execute(
        "CREATE TYPE quotestatus AS ENUM ('pending', 'priced', 'accepted', 'rejected', 'countered')"
    )

    # Drop the old status column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status")

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

    # Drop the enum type constraint
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status")

    op.execute("DROP TYPE quotestatus")

    # Create old enum type
    op.execute(
        "CREATE TYPE quotestatus AS ENUM ('pending', 'priced', 'accepted', 'rejected')"
    )

    # Add old status column
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending", "priced", "accepted", "rejected", name="quotestatus"
                ),
                nullable=True,
            )
        )

    # Copy data back (excluding 'countered' values)
    op.execute(
        "UPDATE quotes SET status = CASE WHEN status_old != 'countered' THEN status_old::quotestatus ELSE NULL END"
    )

    # Drop temporary column and buyer_max_price
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.drop_column("status_old")
        batch_op.drop_column("buyer_max_price")
