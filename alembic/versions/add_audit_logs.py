"""add_audit_logs

Revision ID: xxxx_add_audit_logs
Revises: 634f04d91d4a
Create Date: 2025-01-07 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "xxxx_add_audit_logs"
down_revision: str | None = "634f04d91d4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create everything with raw SQL to avoid conflicts
    op.execute(
        """
        -- Create enum type if it doesn't exist
        DO $$ BEGIN
            CREATE TYPE auditaction AS ENUM (
                'quote_created',
                'negotiation_turn',
                'quote_accepted',
                'quote_rejected',
                'payment_succeeded',
                'payment_failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        -- Create audit_logs table
        CREATE TABLE audit_logs (
            id SERIAL PRIMARY KEY,
            quote_id INTEGER REFERENCES quotes(id),
            action auditaction,
            payload JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- Create indexes
        CREATE INDEX ix_audit_logs_quote_id ON audit_logs (quote_id);
        CREATE INDEX ix_audit_logs_action ON audit_logs (action);
    """
    )


def downgrade() -> None:
    # Drop everything with raw SQL
    op.execute(
        """
        DROP INDEX IF EXISTS ix_audit_logs_action;
        DROP INDEX IF EXISTS ix_audit_logs_quote_id;
        DROP TABLE IF EXISTS audit_logs;
        DROP TYPE IF EXISTS auditaction;
    """
    )
