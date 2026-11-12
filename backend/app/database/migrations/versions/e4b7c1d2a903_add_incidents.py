"""add incident reporting and management"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "e4b7c1d2a903"
down_revision: Union[str, Sequence[str], None] = "d27f61a93b40"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
TECHNICIAN_ROLE_ID = UUID("c68a91f2-d743-4c00-9000-000000000001")
PERMISSIONS = [
    {
        "id": UUID("e4b7c1d2-a903-4bb7-9300-000000000001"),
        "code": "incidents.create",
        "name": "Report Incidents",
        "module": "incident_management",
        "action": "create",
        "description": "Report incidents within authorized site scope.",
    },
    {
        "id": UUID("e4b7c1d2-a903-4bb7-9300-000000000002"),
        "code": "incidents.view",
        "name": "View Incidents",
        "module": "incident_management",
        "action": "view",
        "description": "View incidents within authorized site scope.",
    },
    {
        "id": UUID("e4b7c1d2-a903-4bb7-9300-000000000003"),
        "code": "incidents.update",
        "name": "Update Incidents",
        "module": "incident_management",
        "action": "update",
        "description": "Update and resolve incidents in an organization.",
    },
]


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("reported_by", sa.Uuid(), nullable=False),
        sa.Column("incident_number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
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
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint(
            "category IN ('safety', 'near_miss', 'equipment_damage', "
            "'environmental', 'security', 'other')",
            name="ck_incidents_category",
        ),
        sa.CheckConstraint(
            "status IN ('reported', 'investigating', 'resolved', 'closed')",
            name="ck_incidents_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reported_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "incident_number",
            name="uq_incident_organization_number",
        ),
    )
    op.create_index(
        "ix_incidents_organization_id",
        "incidents",
        ["organization_id"],
    )
    op.create_index("ix_incidents_site_id", "incidents", ["site_id"])
    op.create_index("ix_incidents_department_id", "incidents", ["department_id"])
    op.create_index("ix_incidents_asset_id", "incidents", ["asset_id"])
    op.create_index("ix_incidents_reported_by", "incidents", ["reported_by"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index(
        "ix_incidents_site_status", "incidents", ["site_id", "status"]
    )
    op.create_index(
        "ix_incidents_org_created", "incidents", ["organization_id", "created_at"]
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
            {"role_id": TECHNICIAN_ROLE_ID, "permission_id": PERMISSIONS[0]["id"]},
            {"role_id": TECHNICIAN_ROLE_ID, "permission_id": PERMISSIONS[1]["id"]},
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
        sa.delete(permissions).where(permissions.c.id.in_(permission_ids))
    )
    op.drop_index("ix_incidents_org_created", table_name="incidents")
    op.drop_index("ix_incidents_site_status", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_reported_by", table_name="incidents")
    op.drop_index("ix_incidents_asset_id", table_name="incidents")
    op.drop_index("ix_incidents_department_id", table_name="incidents")
    op.drop_index("ix_incidents_site_id", table_name="incidents")
    op.drop_index("ix_incidents_organization_id", table_name="incidents")
    op.drop_table("incidents")
