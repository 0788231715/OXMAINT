"""add organization-scoped operations reporting permission"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "b10c00000001"
down_revision: Union[str, Sequence[str], None] = "a10c00000001"
branch_labels = None
depends_on = None

MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
PERMISSION = {
    "id": UUID("b10c0000-0001-4b10-8c00-000000000001"),
    "code": "reports.view",
    "name": "View Operations Reports",
    "module": "reports",
    "action": "view",
    "description": "View organization reporting aggregates within authorized site and department scope.",
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
