from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "work_order_number",
            name="uq_maintenance_work_order_org_number",
        ),
        CheckConstraint(
            "work_order_type IN ('preventive', 'corrective')",
            name="ck_maintenance_work_orders_type",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_maintenance_work_orders_priority",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'waiting', 'completed', 'cancelled')",
            name="ck_maintenance_work_orders_status",
        ),
        Index(
            "ix_maintenance_work_orders_site_status",
            "site_id",
            "status",
        ),
        Index(
            "ix_maintenance_work_orders_org_scheduled",
            "organization_id",
            "scheduled_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    work_order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    work_order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="scheduled", nullable=False, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completion_note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
