from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.asset import Asset
from backend.app.database.models.identity import User
from backend.app.modules.asset_management.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetRead,
    AssetListResponse,
)
from backend.app.modules.asset_management.services.asset_service import (
    create_asset,
    update_asset,
    list_accessible_assets,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


router = APIRouter(
    prefix="/assets",
    tags=["Asset Management"],
)


AssetStatus = Literal[
    "in_service",
    "under_maintenance",
    "out_of_service",
    "retired",
]

AssetCriticality = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


@router.post(
    "",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_endpoint(
    data: AssetCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.create")
    ),
    db: Session = Depends(get_db),
):
    if data.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied.",
        )

    if not has_site_access(
        db,
        current_user.id,
        data.site_id,
        organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this site.",
        )

    if data.department_id is not None:
        if not has_department_access(
            db,
            current_user.id,
            data.department_id,
            organization_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this department.",
            )

    if data.parent_asset_id is not None:
        parent = db.get(Asset, data.parent_asset_id)

        if parent is not None and not has_site_access(
            db,
            current_user.id,
            parent.site_id,
            organization_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the parent asset's site.",
            )

    asset = create_asset(db, data)

    db.commit()
    db.refresh(asset)

    return asset


@router.get(
    "",
    response_model=AssetListResponse,
)
def list_assets_endpoint(
    organization_id: UUID = Query(...),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=150),
    asset_status: AssetStatus | None = Query(
        default=None,
        alias="status",
    ),
    criticality: AssetCriticality | None = Query(default=None),
    current_user: User = Depends(
        require_permission("assets.view")
    ),
    db: Session = Depends(get_db),
):
    return list_accessible_assets(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        search=search,
        asset_status=asset_status,
        criticality=criticality,
    )

@router.get(
    "/{asset_id}",
    response_model=AssetRead,
)
def get_asset_endpoint(
    asset_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.view")
    ),
    db: Session = Depends(get_db),
):
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.is_active.is_(True),
        )
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    if not has_site_access(
        db, current_user.id, asset.site_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site access denied.",
        )

    if asset.department_id is not None and not has_department_access(
        db, current_user.id, asset.department_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied.",
        )

    return asset


@router.patch(
    "/{asset_id}",
    response_model=AssetRead,
)
def update_asset_endpoint(
    asset_id: UUID,
    data: AssetUpdate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.update")
    ),
    db: Session = Depends(get_db),
):
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.is_active.is_(True),
        )
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    # Verify access to the asset's current location.
    if not has_site_access(
        db, current_user.id, asset.site_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current site access denied.",
        )

    if asset.department_id is not None and not has_department_access(
        db, current_user.id, asset.department_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current department access denied.",
        )

    changes = data.model_dump(exclude_unset=True)

    target_site_id = changes.get("site_id", asset.site_id)
    target_department_id = changes.get(
        "department_id", asset.department_id
    )
    target_parent_id = changes.get(
        "parent_asset_id", asset.parent_asset_id
    )

    # Verify access to the requested destination.
    if not has_site_access(
        db, current_user.id, target_site_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Target site access denied.",
        )

    if target_department_id is not None and not has_department_access(
        db, current_user.id, target_department_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Target department access denied.",
        )

    if target_parent_id is not None:
        parent = db.scalar(
            select(Asset).where(
                Asset.id == target_parent_id,
                Asset.organization_id == organization_id,
                Asset.is_active.is_(True),
            )
        )

        if parent is not None and not has_site_access(
            db, current_user.id, parent.site_id, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent asset site access denied.",
            )

        if parent is not None and parent.department_id is not None:
            if not has_department_access(
                db,
                current_user.id,
                parent.department_id,
                organization_id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Parent asset department access denied.",
                )

    try:
        updated_asset = update_asset(db, asset, data)
        db.commit()
        db.refresh(updated_asset)
        return updated_asset
    except Exception:
        db.rollback()
        raise

