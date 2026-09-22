"""Create bills and allocations.

Revision ID: 0002_bills_allocations
Revises: 0001_initial_identity
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_bills_allocations"
down_revision = "0001_initial_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("payer_membership_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "split_method",
            sa.Enum(
                "EQUAL", native_enum=False, create_constraint=True, name="ck_bills_split_method"
            ),
            server_default="EQUAL",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bills"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], name="fk_bills_household_id"),
        sa.ForeignKeyConstraint(
            ["payer_membership_id"],
            ["household_memberships.id"],
            name="fk_bills_payer_membership_id",
        ),
        sa.CheckConstraint("amount_minor > 0", name="ck_bills_amount_positive"),
    )
    op.create_index("ix_bills_household_id", "bills", ["household_id"])
    op.create_index("ix_bills_payer_membership_id", "bills", ["payer_membership_id"])
    op.create_table(
        "allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_allocations"),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], name="fk_allocations_bill_id"),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["household_memberships.id"], name="fk_allocations_membership_id"
        ),
        sa.UniqueConstraint("bill_id", "membership_id", name="uq_allocations_bill_membership"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_allocations_amount_nonnegative"),
    )
    op.create_index("ix_allocations_membership_id", "allocations", ["membership_id"])


def downgrade() -> None:
    op.drop_index("ix_allocations_membership_id", table_name="allocations")
    op.drop_table("allocations")
    op.drop_index("ix_bills_payer_membership_id", table_name="bills")
    op.drop_index("ix_bills_household_id", table_name="bills")
    op.drop_table("bills")
