"""add asset management permissions

Revision ID: 7f4c2b19a6d3
Revises: 0dddc969cbf3
"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "7f4c2b19a6d3"
down_revision: Union[str, Sequence[str], None] = "0dddc969cbf3"
branch_labels = None
depends_on = None

MAINTENANCE_MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")

PERMISSIONS = [
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000001"),
        "code": "assets.create",
        "name": "Create Assets",
        "module": "asset_management",
        "action": "create",
        "description": "Create assets within authorized organizational scope.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000002"),
        "code": "assets.view",
        "name": "View Assets",
        "module": "asset_management",
        "action": "view",
        "description": "View assets within authorized organizational scope.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000003"),
        "code": "assets.update",
        "name": "Update Assets",
        "module": "asset_management",
        "action": "update",
        "description": "Update assets within authorized organizational scope.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000004"),
        "code": "assets.categories.create",
        "name": "Create Asset Categories",
        "module": "asset_management",
        "action": "create",
        "description": "Create asset categories in an organization.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000005"),
        "code": "assets.categories.view",
        "name": "View Asset Categories",
        "module": "asset_management",
        "action": "view",
        "description": "View asset categories in an organization.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000006"),
        "code": "assets.categories.update",
        "name": "Update Asset Categories",
        "module": "asset_management",
        "action": "update",
        "description": "Update asset categories in an organization.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000007"),
        "code": "assets.categories.deactivate",
        "name": "Deactivate Asset Categories",
        "module": "asset_management",
        "action": "deactivate",
        "description": "Deactivate asset categories in an organization.",
    },
    {
        "id": UUID("7f4c2b19-a6d3-4f20-9b01-000000000008"),
        "code": "assets.categories.reactivate",
        "name": "Reactivate Asset Categories",
        "module": "asset_management",
        "action": "reactivate",
        "description": "Reactivate asset categories in an organization.",
    },
]


def upgrade() -> None:
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
            {
                "role_id": MAINTENANCE_MANAGER_ROLE_ID,
                "permission_id": permission["id"],
            }
            for permission in PERMISSIONS
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
    permission_ids = [permission["id"] for permission in PERMISSIONS]

    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.permission_id.in_(permission_ids)
        )
    )
    op.execute(
        sa.delete(permissions).where(permissions.c.id.in_(permission_ids))
    )
