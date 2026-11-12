"""add scheduled maintenance work orders"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "9c2e6f4a1b80"
down_revision: Union[str, Sequence[str], None] = "e4b7c1d2a903"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
TECHNICIAN_ROLE_ID = UUID("c68a91f2-d743-4c00-9000-000000000001")
PERMISSIONS = [
    {
        "id": UUID("9c2e6f4a-1b80-4c12-8d00-000000000001"),
        "code": "maintenance.view",
        "name": "View Maintenance Work Orders",
        "module": "maintenance_calendar",
        "action": "view",
        "description": "View work orders within authorized site scope.",
    },
    {
        "id": UUID("9c2e6f4a-1b80-4c12-8d00-000000000002"),
        "code": "maintenance.create",
        "name": "Create Maintenance Work Orders",
        "module": "maintenance_calendar",
        "action": "create",
        "description": "Schedule work orders for authorized assets.",
    },
    {
        "id": UUID("9c2e6f4a-1b80-4c12-8d00-000000000003"),
        "code": "maintenance.transition",
        "name": "Update Maintenance Work Order Status",
        "module": "maintenance_calendar",
        "action": "transition",
        "description": "Track work order progress and completion.",
    },
]


def upgrade() -> None:
    op.create_table(
        "maintenance_work_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("work_order_number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("work_order_type", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "work_order_type IN ('preventive', 'corrective')",
            name="ck_maintenance_work_orders_type",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_maintenance_work_orders_priority",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'waiting', 'completed', 'cancelled')",
            name="ck_maintenance_work_orders_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "work_order_number",
            name="uq_maintenance_work_order_org_number",
        ),
    )
    for column in ("organization_id", "asset_id", "site_id", "department_id", "created_by", "status"):
        op.create_index(
            f"ix_maintenance_work_orders_{column}",
            "maintenance_work_orders",
            [column],
        )
    op.create_index(
        "ix_maintenance_work_orders_site_status",
        "maintenance_work_orders",
        ["site_id", "status"],
    )
    op.create_index(
        "ix_maintenance_work_orders_org_scheduled",
        "maintenance_work_orders",
        ["organization_id", "scheduled_at"],
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
            {"role_id": TECHNICIAN_ROLE_ID, "permission_id": item["id"]}
            for item in PERMISSIONS
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
        "ix_maintenance_work_orders_org_scheduled",
        table_name="maintenance_work_orders",
    )
    op.drop_index(
        "ix_maintenance_work_orders_site_status",
        table_name="maintenance_work_orders",
    )
    for column in reversed(
        ("organization_id", "asset_id", "site_id", "department_id", "created_by", "status")
    ):
        op.drop_index(
            f"ix_maintenance_work_orders_{column}",
            table_name="maintenance_work_orders",
        )
    op.drop_table("maintenance_work_orders")
