"""add idempotent offline synchronization receipts"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c30c00000001"
down_revision: Union[str, Sequence[str], None] = "c20c00000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synchronization_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=80), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "organization_id",
            "operation_id",
            name="uq_synchronization_receipts_user_org_operation",
        ),
    )
    op.create_index(
        "ix_synchronization_receipts_user_org_created",
        "synchronization_receipts",
        ["user_id", "organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_synchronization_receipts_user_org_created",
        table_name="synchronization_receipts",
    )
    op.drop_table("synchronization_receipts")
