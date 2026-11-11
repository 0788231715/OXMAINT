from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base


class AssetCategory(Base):
    __tablename__ = "asset_categories"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_asset_category_organization_code",
        ),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[Uuid] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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

    assets: Mapped[list["Asset"]] = relationship(
        back_populates="category"
    )


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "asset_tag",
            name="uq_asset_organization_tag",
        ),
        Index("ix_assets_site_status", "site_id", "status"),
        Index("ix_assets_department_status", "department_id", "status"),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)

    organization_id: Mapped[Uuid] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[Uuid] = mapped_column(
        ForeignKey("asset_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[Uuid] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[Uuid | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        index=True,
    )
    parent_asset_id: Mapped[Uuid | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        index=True,
    )

    asset_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    manufacturer: Mapped[str | None] = mapped_column(String(150))
    model_number: Mapped[str | None] = mapped_column(String(150))
    serial_number: Mapped[str | None] = mapped_column(String(150))
    year_manufactured: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(
        String(40), default="in_service", nullable=False
    )
    criticality: Mapped[str] = mapped_column(
        String(30), default="medium", nullable=False
    )

    installation_date: Mapped[date | None] = mapped_column(Date)
    commissioning_date: Mapped[date | None] = mapped_column(Date)
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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

    category: Mapped["AssetCategory"] = relationship(
        back_populates="assets"
    )
    parent_asset: Mapped["Asset | None"] = relationship(
        remote_side="Asset.id",
        back_populates="child_assets",
    )
    child_assets: Mapped[list["Asset"]] = relationship(
        back_populates="parent_asset"
    )
