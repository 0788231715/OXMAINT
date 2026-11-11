"""add service request workflow permissions

Revision ID: 0dddc969cbf3
Revises: c31a8f72d940
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0dddc969cbf3"
down_revision: Union[str, Sequence[str], None] = "c31a8f72d940"
branch_labels = None
depends_on = None


PERMISSIONS = [
    (
        "0dddc969-cbf3-4a21-9a12-000000000001",
        "service_requests.create",
        "Create Service Requests",
        "create",
        "Create maintenance and service requests.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000002",
        "service_requests.view",
        "View Service Requests",
        "view",
        "View service requests within authorized organizational scope.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000003",
        "service_requests.update",
        "Update Service Requests",
        "update",
        "Update eligible service request details.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000004",
        "service_requests.review",
        "Review Service Requests",
        "review",
        "Review submitted service requests.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000005",
        "service_requests.assign",
        "Assign Service Requests",
        "assign",
        "Assign service requests to authorized personnel.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000006",
        "service_requests.reject",
        "Reject Service Requests",
        "reject",
        "Reject service requests with a recorded reason.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000007",
        "service_requests.transition",
        "Change Service Request Status",
        "transition",
        "Change service request status through permitted transitions.",
    ),
    (
        "0dddc969-cbf3-4a21-9a12-000000000008",
        "service_requests.comment",
        "Comment on Service Requests",
        "comment",
        "Add comments to eligible service requests.",
    ),
]


def upgrade() -> None:
    for permission_id, code, name, action, description in PERMISSIONS:
        op.execute(
            f"""
            INSERT INTO permissions
                (id, code, name, module, action, description)
            VALUES
                (
                    '{permission_id}',
                    '{code}',
                    '{name}',
                    'service_requests',
                    '{action}',
                    '{description}'
                )
            """
        )


def downgrade() -> None:
    for permission_id, *_ in reversed(PERMISSIONS):
        op.execute(
            f"""
            DELETE FROM role_permissions
            WHERE permission_id = '{permission_id}'
            """
        )

        op.execute(
            f"""
            DELETE FROM permissions
            WHERE id = '{permission_id}'
            """
        )
