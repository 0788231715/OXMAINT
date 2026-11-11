"""add role-gated user registration and technician role"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "c68a91f2d743"
down_revision: Union[str, Sequence[str], None] = "b8e4d72a19c5"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
TECHNICIAN_ROLE_ID = UUID("c68a91f2-d743-4c00-9000-000000000001")
CREATE_USERS_PERMISSION_ID = UUID("c68a91f2-d743-4c00-9000-000000000002")

TECHNICIAN_PERMISSION_IDS = [
    UUID("7f4c2b19-a6d3-4f20-9b01-000000000002"),
    UUID("7f4c2b19-a6d3-4f20-9b01-000000000005"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000001"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000002"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000003"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000007"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000008"),
]


def upgrade() -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
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

    op.bulk_insert(
        roles,
        [{
            "id": TECHNICIAN_ROLE_ID,
            "code": "maintenance_technician",
            "name": "Maintenance Technician",
            "description": "Scoped operational role for maintenance technicians.",
            "is_system": True,
            "is_active": True,
        }],
    )
    op.bulk_insert(
        permissions,
        [{
            "id": CREATE_USERS_PERMISSION_ID,
            "code": "users.create",
            "name": "Register Organization Users",
            "module": "user_management",
            "action": "create",
            "description": "Register maintenance technicians in an organization.",
        }],
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": MANAGER_ROLE_ID, "permission_id": CREATE_USERS_PERMISSION_ID},
            *[
                {"role_id": TECHNICIAN_ROLE_ID, "permission_id": permission_id}
                for permission_id in TECHNICIAN_PERMISSION_IDS
            ],
        ],
    )


def downgrade() -> None:
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    roles = sa.table("roles", sa.column("id", sa.Uuid()))
    permissions = sa.table("permissions", sa.column("id", sa.Uuid()))

    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.permission_id == CREATE_USERS_PERMISSION_ID
        )
    )
    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.role_id == TECHNICIAN_ROLE_ID
        )
    )
    op.execute(sa.delete(roles).where(roles.c.id == TECHNICIAN_ROLE_ID))
    op.execute(
        sa.delete(permissions).where(
            permissions.c.id == CREATE_USERS_PERMISSION_ID
        )
    )