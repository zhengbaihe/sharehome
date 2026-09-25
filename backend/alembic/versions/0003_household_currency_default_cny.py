"""Change the household currency default to CNY without changing existing rows.

Revision ID: 0003_household_currency_cny
Revises: 0002_bills_allocations
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_household_currency_cny"
down_revision = "0002_bills_allocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("households", "currency", existing_type=sa.String(3), server_default="CNY")


def downgrade() -> None:
    op.alter_column("households", "currency", existing_type=sa.String(3), server_default="MYR")
