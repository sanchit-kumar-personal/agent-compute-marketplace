"""Add reservations table and update compute resources

Revision ID: add_inventory_v1
Revises: xxxx_add_audit_logs
Create Date: 2024-12-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_inventory_v1"
down_revision = "xxxx_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    # Create reservations table
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id"),
    )

    # Update compute_resources table with default status
    op.alter_column(
        "compute_resources",
        "status",
        existing_type=sa.VARCHAR(length=20),
        nullable=True,
        server_default="available",
    )


def downgrade():
    # Remove server default from compute_resources
    op.alter_column(
        "compute_resources",
        "status",
        existing_type=sa.VARCHAR(length=20),
        nullable=True,
        server_default=None,
    )

    # Drop reservations table
    op.drop_table("reservations")
