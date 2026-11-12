"""add organization settings permission"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "d10c00000001"
down_revision: Union[str, Sequence[str], None] = "c30c00000001"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
PERMISSION = {
    "id": UUID("d10c0000-0001-4d10-8c00-000000000001"),
    "code": "organizations.update",
    "name": "Update Organization Settings",
    "module": "system_settings",
    "action": "update",
    "description": "Update organization profile settings.",
}


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
    op.bulk_insert(permissions, [PERMISSION])
    op.bulk_insert(
        role_permissions,
        [{"role_id": MANAGER_ROLE_ID, "permission_id": PERMISSION["id"]}],
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
    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.permission_id == PERMISSION["id"]
        )
    )
    op.execute(
        sa.delete(permissions).where(
            permissions.c.id == PERMISSION["id"]
        )
    )
