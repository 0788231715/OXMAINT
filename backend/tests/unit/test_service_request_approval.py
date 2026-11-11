from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.database.models.service_request import (
    RequestApproval,
    RequestStatusHistory,
)
from backend.app.modules.service_requests.schemas.service_request import (
    RequestApprovalInput,
    RequestRejectionInput,
)
from backend.app.modules.service_requests.services import (
    service_request_service as service,
)


def test_approval_moves_request_from_review_to_approved(monkeypatch):
    requester_id = uuid4()
    approver_id = uuid4()
    request = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        requester_id=requester_id,
        status="under_review",
    )
    approver = SimpleNamespace(is_active=True)
    db = MagicMock()
    db.get.return_value = approver
    db.scalar.return_value = None

    monkeypatch.setattr(service, "has_permission", lambda *args: True)

    approval = service.record_request_approval(
        db=db,
        request=request,
        data=RequestApprovalInput(decision="approved"),
        approver_id=approver_id,
    )

    added_records = [call.args[0] for call in db.add.call_args_list]
    status_history = next(
        record
        for record in added_records
        if isinstance(record, RequestStatusHistory)
    )

    assert isinstance(approval, RequestApproval)
    assert request.status == "approved"
    assert status_history.previous_status == "under_review"
    assert status_history.new_status == "approved"
    assert status_history.changed_by == approver_id


def test_completed_request_cannot_be_rejected():
    request = SimpleNamespace(status="completed")

    with pytest.raises(HTTPException) as error:
        service.reject_service_request(
            db=MagicMock(),
            request=request,
            data=RequestRejectionInput(reason="Work was completed."),
            rejected_by=uuid4(),
        )

    assert error.value.status_code == 409
