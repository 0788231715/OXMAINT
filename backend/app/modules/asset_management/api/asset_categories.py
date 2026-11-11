from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.asset_management.schemas.asset import (
    AssetCategoryCreate,
    AssetCategoryRead,
    AssetCategoryListResponse,
    AssetCategoryUpdate,
)
from backend.app.modules.asset_management.services.asset_service import (
    create_asset_category,
    list_asset_categories,
    get_asset_category,
    update_asset_category,
    deactivate_asset_category,
    reactivate_asset_category,
)


router = APIRouter(
    prefix="/asset-categories",
    tags=["Asset Categories"],
)


@router.post(
    "",
    response_model=AssetCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_category_endpoint(
    data: AssetCategoryCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.categories.create")
    ),
    db: Session = Depends(get_db),
):
    if data.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied.",
        )

    try:
        category = create_asset_category(db, data)
        db.commit()
        db.refresh(category)
        return category
    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=AssetCategoryListResponse,
)
def list_asset_categories_endpoint(
    organization_id: UUID = Query(...),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=150),
    current_user: User = Depends(
        require_permission("assets.categories.view")
    ),
    db: Session = Depends(get_db),
):
    return list_asset_categories(
        db=db,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        search=search,
    )


@router.get(
    "/{category_id}",
    response_model=AssetCategoryRead,
)
def get_asset_category_endpoint(
    category_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.categories.view")
    ),
    db: Session = Depends(get_db),
):
    return get_asset_category(
        db=db,
        organization_id=organization_id,
        category_id=category_id,
    )

@router.patch(
    "/{category_id}",
    response_model=AssetCategoryRead,
)
def update_asset_category_endpoint(
    category_id: UUID,
    data: AssetCategoryUpdate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.categories.update")
    ),
    db: Session = Depends(get_db),
):
    try:
        category = update_asset_category(
            db=db,
            organization_id=organization_id,
            category_id=category_id,
            changes=data.model_dump(exclude_unset=True),
        )
        db.commit()
        db.refresh(category)
        return category
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{category_id}/deactivate",
    response_model=AssetCategoryRead,
)
def deactivate_asset_category_endpoint(
    category_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.categories.deactivate")
    ),
    db: Session = Depends(get_db),
):
    try:
        category = deactivate_asset_category(
            db=db,
            organization_id=organization_id,
            category_id=category_id,
        )
        db.commit()
        db.refresh(category)
        return category
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{category_id}/reactivate",
    response_model=AssetCategoryRead,
)
def reactivate_asset_category_endpoint(
    category_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("assets.categories.reactivate")
    ),
    db: Session = Depends(get_db),
):
    try:
        category = reactivate_asset_category(
            db=db,
            organization_id=organization_id,
            category_id=category_id,
        )
        db.commit()
        db.refresh(category)
        return category
    except Exception:
        db.rollback()
        raise

