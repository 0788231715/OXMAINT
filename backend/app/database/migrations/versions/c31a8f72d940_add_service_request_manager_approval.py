"""add service request manager approval permission and role

Revision ID: c31a8f72d940
Revises: 9947d9520724
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c31a8f72d940"
down_revision: Union[str, Sequence[str], None] = "9947d9520724"
branch_labels = None
depends_on = None

ROLE_ID = "c31a8f72-d940-4a21-9a12-000000000001"
PERMISSION_ID = "c31a8f72-d940-4a21-9a12-000000000002"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO roles
            (id, code, name, description, is_system, is_active)
        VALUES
            (
                '{ROLE_ID}',
                'maintenance_manager',
                'Maintenance Manager',
                'Organization-scoped role for approving high-priority, urgent, and safety-critical service requests.',
                TRUE,
                TRUE
            )
    """)

    op.execute(f"""
        INSERT INTO permissions
            (id, code, name, module, action, description)
        VALUES
            (
                '{PERMISSION_ID}',
                'service_requests.approve',
                'Approve Service Requests',
                'service_requests',
                'approve',
                'Approve or reject service requests requiring manager authorization.'
            )
    """)

    op.execute(f"""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES ('{ROLE_ID}', '{PERMISSION_ID}')
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM role_permissions
        WHERE role_id = '{ROLE_ID}'
          AND permission_id = '{PERMISSION_ID}'
    """)

    # Foreign-key constraints prevent deleting records still in use.
    op.execute(f"DELETE FROM roles WHERE id = '{ROLE_ID}'")
    op.execute(f"DELETE FROM permissions WHERE id = '{PERMISSION_ID}'")
