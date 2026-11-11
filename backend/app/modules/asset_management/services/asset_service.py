from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models.organization import (
    Organization,
    Department,
    Site,
)
from backend.app.database.models.asset import Asset, AssetCategory


VALID_STATUSES = {
    "in_service",
    "under_maintenance",
    "out_of_service",
    "retired",
}

VALID_CRITICALITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


def _validate_organization(db: Session, organization_id: UUID):
    organization = db.get(Organization, organization_id)

    if organization is None or not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization not found.",
        )

    return organization


def _validate_asset_references(
    db: Session,
    organization_id: UUID,
    values: dict,
    current_asset_id: UUID | None = None,
):
    _validate_organization(db, organization_id)

    category_id = values.get("category_id")
    site_id = values.get("site_id")
    department_id = values.get("department_id")
    parent_asset_id = values.get("parent_asset_id")

    if category_id is None or site_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An asset must have a category and site.",
        )

    category = db.get(AssetCategory, category_id)

    if (
        category is None
        or not category.is_active
        or category.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The selected category is unavailable for this organization.",
        )

    site = db.get(Site, site_id)

    if (
        site is None
        or not site.is_active
        or site.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The selected site is unavailable for this organization.",
        )

    if department_id is not None:
        department = db.get(Department, department_id)

        if (
            department is None
            or not department.is_active
            or department.organization_id != organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The selected department is unavailable for this organization.",
            )

    if parent_asset_id is not None:
        if parent_asset_id == current_asset_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An asset cannot be its own parent.",
            )

        parent = db.get(Asset, parent_asset_id)

        if (
            parent is None
            or not parent.is_active
            or parent.organization_id != organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The selected parent asset is unavailable.",
            )

        # Prevent circular parent-child relationships.
        visited = set()
        ancestor = parent

        while ancestor is not None:
            if ancestor.id == current_asset_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="This parent assignment would create an asset hierarchy cycle.",
                )

            if ancestor.id in visited:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An existing circular asset hierarchy was detected.",
                )

            visited.add(ancestor.id)

            if ancestor.parent_asset_id is None:
                break

            ancestor = db.get(Asset, ancestor.parent_asset_id)

    if values.get("status") not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid asset status.",
        )

    if values.get("criticality") not in VALID_CRITICALITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid asset criticality.",
        )


def _check_duplicate_asset_tag(
    db: Session,
    organization_id: UUID,
    asset_tag: str,
    exclude_asset_id: UUID | None = None,
):
    query = select(Asset).where(
        Asset.organization_id == organization_id,
        Asset.asset_tag == asset_tag,
    )

    if exclude_asset_id is not None:
        query = query.where(Asset.id != exclude_asset_id)

    existing = db.scalar(query)

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this tag already exists in the organization.",
        )


def create_asset(db: Session, data):
    values = data.model_dump()

    _validate_asset_references(
        db,
        values["organization_id"],
        values,
    )

    _check_duplicate_asset_tag(
        db,
        values["organization_id"],
        values["asset_tag"],
    )

    asset = Asset(**values)

    db.add(asset)
    db.flush()

    return asset


def update_asset(db: Session, asset: Asset, data):
    changes = data.model_dump(exclude_unset=True)

    # Organization ownership is immutable through ordinary updates.
    values = {
        "category_id": asset.category_id,
        "site_id": asset.site_id,
        "department_id": asset.department_id,
        "parent_asset_id": asset.parent_asset_id,
        "status": asset.status,
        "criticality": asset.criticality,
        **changes,
    }

    for field in ("category_id", "site_id", "status", "criticality"):
        if values[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null.",
            )

    _validate_asset_references(
        db,
        asset.organization_id,
        values,
        current_asset_id=asset.id,
    )

    new_name = values.get("name", asset.name)

    if new_name is None or not new_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Asset name cannot be blank.",
        )

    new_tag = values.get("asset_tag", asset.asset_tag)

    if new_tag is None or not new_tag.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Asset tag cannot be blank.",
        )

    _check_duplicate_asset_tag(
        db,
        asset.organization_id,
        new_tag,
        exclude_asset_id=asset.id,
    )

    for field, value in changes.items():
        setattr(asset, field, value)

    db.flush()

    return asset


def create_asset_category(db: Session, data):
    values = data.model_dump()

    _validate_organization(db, values["organization_id"])

    existing = db.scalar(
        select(AssetCategory).where(
            AssetCategory.organization_id == values["organization_id"],
            AssetCategory.code == values["code"],
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This asset category code already exists in the organization.",
        )

    category = AssetCategory(**values)

    db.add(category)
    db.flush()

    return category

def _build_accessible_assets_query(
    user_id: UUID,
    organization_id: UUID,
):
    """Build a query restricted to the user's authorized asset scope."""

    from datetime import datetime, timezone

    from sqlalchemy import or_
    from backend.app.database.models.identity import (
        User,
        UserDepartmentAccess,
        UserSiteAccess,
    )

    now = datetime.now(timezone.utc)
    system_admin = (
        select(User.is_system_admin)
        .where(User.id == user_id)
        .scalar_subquery()
    )

    site_access = (
        select(UserSiteAccess.id)
        .join(Site, Site.id == UserSiteAccess.site_id)
        .where(
            UserSiteAccess.user_id == user_id,
            UserSiteAccess.site_id == Asset.site_id,
            Site.organization_id == organization_id,
            Site.is_active.is_(True),
            (
                UserSiteAccess.expires_at.is_(None)
                | (UserSiteAccess.expires_at > now)
            ),
        )
        .exists()
    )

    department_access = (
        select(UserDepartmentAccess.id)
        .join(
            Department,
            Department.id == UserDepartmentAccess.department_id,
        )
        .where(
            UserDepartmentAccess.user_id == user_id,
            UserDepartmentAccess.department_id == Asset.department_id,
            Department.organization_id == organization_id,
            Department.is_active.is_(True),
            (
                UserDepartmentAccess.expires_at.is_(None)
                | (UserDepartmentAccess.expires_at > now)
            ),
        )
        .exists()
    )

    return (
        select(Asset)
        .join(
            Organization,
            Organization.id == Asset.organization_id,
        )
        .where(
            Asset.organization_id == organization_id,
            Asset.is_active.is_(True),
            Organization.is_active.is_(True),
            or_(system_admin.is_(True), site_access),
            or_(
                system_admin.is_(True),
                Asset.department_id.is_(None),
                department_access,
            ),
        )
    )


def list_accessible_assets(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    asset_status: str | None = None,
    criticality: str | None = None,
) -> dict:
    """Return authorized assets with filtering and pagination."""

    from math import ceil
    from sqlalchemy import func, or_

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100.")

    if asset_status is not None and asset_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid asset status filter.",
        )

    if criticality is not None and criticality not in VALID_CRITICALITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid asset criticality filter.",
        )

    statement = _build_accessible_assets_query(
        user_id=user_id,
        organization_id=organization_id,
    )

    if search is not None:
        search = search.strip()

    if search:
        term = f"%{search}%"

        statement = statement.where(
            or_(
                Asset.asset_tag.ilike(term),
                Asset.name.ilike(term),
                Asset.manufacturer.ilike(term),
                Asset.serial_number.ilike(term),
            )
        )

    if asset_status is not None:
        statement = statement.where(
            Asset.status == asset_status
        )

    if criticality is not None:
        statement = statement.where(
            Asset.criticality == criticality
        )

    count_statement = (
        select(func.count())
        .select_from(statement.order_by(None).subquery())
    )

    total = db.scalar(count_statement) or 0

    items_statement = (
        statement
        .order_by(Asset.name.asc(), Asset.id.asc())
        .offset(offset)
        .limit(limit)
    )

    items = list(db.scalars(items_statement).all())

    page = (offset // limit) + 1
    total_pages = ceil(total / limit) if total else 0

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "page": page,
        "total_pages": total_pages,
        "has_more": offset + len(items) < total,
    }


def list_asset_categories(
    db: Session,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> dict:
    """List active categories belonging to an active organization."""

    from math import ceil
    from sqlalchemy import func, or_

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100.")

    _validate_organization(db, organization_id)

    statement = select(AssetCategory).where(
        AssetCategory.organization_id == organization_id,
        AssetCategory.is_active.is_(True),
    )

    if search is not None:
        search = search.strip()

    if search:
        term = f"%{search}%"
        statement = statement.where(
            or_(
                AssetCategory.name.ilike(term),
                AssetCategory.code.ilike(term),
                AssetCategory.description.ilike(term),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
    ) or 0

    items = list(
        db.scalars(
            statement
            .order_by(AssetCategory.name.asc(), AssetCategory.id.asc())
            .offset(offset)
            .limit(limit)
        ).all()
    )

    page = (offset // limit) + 1
    total_pages = ceil(total / limit) if total else 0

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "page": page,
        "total_pages": total_pages,
        "has_more": offset + len(items) < total,
    }


def get_asset_category(
    db: Session,
    organization_id: UUID,
    category_id: UUID,
):
    """Retrieve one active category within the requested organization."""

    _validate_organization(db, organization_id)

    category = db.scalar(
        select(AssetCategory).where(
            AssetCategory.id == category_id,
            AssetCategory.organization_id == organization_id,
            AssetCategory.is_active.is_(True),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset category not found.",
        )

    return category

def update_asset_category(
    db: Session,
    organization_id: UUID,
    category_id: UUID,
    changes: dict,
):
    """Update an active category without changing its identity or code."""

    _validate_organization(db, organization_id)

    category = db.scalar(
        select(AssetCategory).where(
            AssetCategory.id == category_id,
            AssetCategory.organization_id == organization_id,
            AssetCategory.is_active.is_(True),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active asset category not found.",
        )

    for field in ("name", "description"):
        if field in changes:
            setattr(category, field, changes[field])

    db.flush()
    return category


def deactivate_asset_category(
    db: Session,
    organization_id: UUID,
    category_id: UUID,
):
    """Deactivate a category while preserving its asset references."""

    _validate_organization(db, organization_id)

    category = db.scalar(
        select(AssetCategory).where(
            AssetCategory.id == category_id,
            AssetCategory.organization_id == organization_id,
            AssetCategory.is_active.is_(True),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active asset category not found.",
        )

    category.is_active = False
    db.flush()
    return category


def reactivate_asset_category(
    db: Session,
    organization_id: UUID,
    category_id: UUID,
):
    """Reactivate a previously deactivated category."""

    _validate_organization(db, organization_id)

    category = db.scalar(
        select(AssetCategory).where(
            AssetCategory.id == category_id,
            AssetCategory.organization_id == organization_id,
            AssetCategory.is_active.is_(False),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inactive asset category not found.",
        )

    category.is_active = True
    db.flush()
    return category

