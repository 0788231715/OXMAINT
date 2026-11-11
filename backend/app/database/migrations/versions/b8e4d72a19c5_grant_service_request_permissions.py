"""grant service request permissions to maintenance managers"""

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4d72a19c5"
down_revision: Union[str, Sequence[str], None] = "7f4c2b19a6d3"
branch_labels = None
depends_on = None

MAINTENANCE_MANAGER_ROLE_ID = UUID("c31a8f72-d940-4a21-9a12-000000000001")
PERMISSION_IDS = [
    UUID("0dddc969-cbf3-4a21-9a12-000000000001"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000002"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000003"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000004"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000005"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000006"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000007"),
    UUID("0dddc969-cbf3-4a21-9a12-000000000008"),
]


def upgrade() -> None:
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permissions,
        [
            {
                "role_id": MAINTENANCE_MANAGER_ROLE_ID,
                "permission_id": permission_id,
            }
            for permission_id in PERMISSION_IDS
        ],
    )


def downgrade() -> None:
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.execute(
        sa.delete(role_permissions).where(
            role_permissions.c.role_id == MAINTENANCE_MANAGER_ROLE_ID,
            role_permissions.c.permission_id.in_(PERMISSION_IDS),
        )
    )