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


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "incident_number",
            name="uq_incident_organization_number",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        CheckConstraint(
            "category IN ('safety', 'near_miss', 'equipment_damage', "
            "'environmental', 'security', 'other')",
            name="ck_incidents_category",
        ),
        CheckConstraint(
            "status IN ('reported', 'investigating', 'resolved', 'closed')",
            name="ck_incidents_status",
        ),
        Index("ix_incidents_site_status", "site_id", "status"),
        Index("ix_incidents_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
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
    asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        index=True,
    )
    reported_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    incident_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="reported", nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolution: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
