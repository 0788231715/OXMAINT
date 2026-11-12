"""add work order technician assignment and handoff history"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "a10c00000001"
down_revision: Union[str, Sequence[str], None] = "9c2e6f4a1b80"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
TECHNICIAN_ROLE_ID = UUID("c68a91f2-d743-4c00-9000-000000000001")
PERMISSIONS = [
    {
        "id": UUID("a10c0000-0001-4a10-8c00-000000000001"),
        "code": "coordination.view",
        "name": "View Work Coordination",
        "module": "coordination",
        "action": "view",
        "description": "View work orders and technician assignments in authorized scope.",
    },
    {
        "id": UUID("a10c0000-0001-4a10-8c00-000000000002"),
        "code": "coordination.assign",
        "name": "Assign Maintenance Work",
        "module": "coordination",
        "action": "assign",
        "description": "Assign and hand off work orders to accessible technicians.",
    },
]


def upgrade() -> None:
    op.create_table(
        "work_order_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("handoff_note", sa.Text(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["maintenance_work_orders.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("work_order_id", "assigned_to", "assigned_by"):
        op.create_index(
            f"ix_work_order_assignments_{column}",
            "work_order_assignments",
            [column],
        )
    op.create_index(
        "ix_work_order_assignments_work_order_assigned",
        "work_order_assignments",
        ["work_order_id", "assigned_at"],
    )

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("module", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(permissions, PERMISSIONS)
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": MANAGER_ROLE_ID, "permission_id": item["id"]}
            for item in PERMISSIONS
        ]
        + [
            {
                "role_id": TECHNICIAN_ROLE_ID,
                "permission_id": PERMISSIONS[0]["id"],
            }
        ],
    )


def downgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("permission_id", sa.Uuid()),
    )
    permission_ids = [item["id"] for item in PERMISSIONS]
    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.permission_id.in_(permission_ids)
        )
    )
    op.execute(
        sa.delete(permissions).where(
            permissions.c.id.in_(permission_ids)
        )
    )
    op.drop_index(
        "ix_work_order_assignments_work_order_assigned",
        table_name="work_order_assignments",
    )
    for column in reversed(("work_order_id", "assigned_to", "assigned_by")):
        op.drop_index(
            f"ix_work_order_assignments_{column}",
            table_name="work_order_assignments",
        )
    op.drop_table("work_order_assignments")
