"""Create users, households, and household memberships.

Revision ID: 0001_initial_identity
Revises: None
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''", name="ck_users_email_normalized"
        ),
    )
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), server_default="MYR", nullable=False),
        sa.Column("timezone", sa.String(64), server_default="Asia/Kuala_Lumpur", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households"),
    )
    op.create_table(
        "household_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "OWNER",
                "MEMBER",
                native_enum=False,
                create_constraint=True,
                name="ck_membership_role",
            ),
            server_default="MEMBER",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "DEPARTED",
                native_enum=False,
                create_constraint=True,
                name="ck_membership_status",
            ),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_household_memberships"),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_household_memberships_household_id"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_household_memberships_user_id"),
        sa.UniqueConstraint(
            "household_id", "user_id", name="uq_household_memberships_household_user"
        ),
    )
    op.create_index("ix_household_memberships_user_id", "household_memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_household_memberships_user_id", table_name="household_memberships")
    op.drop_table("household_memberships")
    op.drop_table("households")
    op.drop_table("users")
