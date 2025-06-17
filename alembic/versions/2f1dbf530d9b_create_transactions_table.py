"""create transactions table

Revision ID: 2f1dbf530d9b
Revises: 2c_buyer_max_price
Create Date: 2025-06-16 16:58:41.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2f1dbf530d9b"
down_revision = "2c_buyer_max_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing transactions table if it exists
    op.drop_table("transactions")

    # Create transactions table with foreign key to quotes
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(9), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
