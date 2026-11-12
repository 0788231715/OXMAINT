from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class WorkOrderAssignment(Base):
    __tablename__ = "work_order_assignments"
    __table_args__ = (
        Index(
            "ix_work_order_assignments_work_order_assigned",
            "work_order_id",
            "assigned_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("maintenance_work_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_to: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    handoff_note: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
