from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class SynchronizationReceipt(Base):
    __tablename__ = "synchronization_receipts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            "operation_id",
            name="uq_synchronization_receipts_user_org_operation",
        ),
        Index(
            "ix_synchronization_receipts_user_org_created",
            "user_id",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
