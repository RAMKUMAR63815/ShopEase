
import os
import secrets
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Product
from app.schemas import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockQuantityRequest,
)
from app.security import CurrentUserId


router = APIRouter(tags=["Products"])

DbSession = Annotated[Session, Depends(get_db)]


# ==================================================
# CATEGORIES
# ==================================================

@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    category_data: CategoryCreate,
    user_id: CurrentUserId,
    db: DbSession,
):
    category = Category(
        name=category_data.name.strip()
    )

    db.add(category)

    try:
        db.commit()
        db.refresh(category)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists",
        )

    return category


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
)
def list_categories(
    db: DbSession,
):
    return db.scalars(
        select(Category).order_by(Category.name)
    ).all()


# ==================================================
# PRODUCTS
# ==================================================

@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product_data: ProductCreate,
    user_id: CurrentUserId,
    db: DbSession,
):
    category = db.get(
        Category,
        product_data.category_id,
    )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    product = Product(
        **product_data.model_dump()
    )

    db.add(product)

    try:
        db.commit()
        db.refresh(product)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create product due to a database conflict",
        )

    return product


@router.get(
    "/products",
    response_model=list[ProductResponse],
)
def list_products(
    db: DbSession,
):
    return db.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    ).all()


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
)
def get_product(
    product_id: int,
    db: DbSession,
):
    product = db.get(
        Product,
        product_id,
    )

    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    user_id: CurrentUserId,
    db: DbSession,
):
    product = db.get(
        Product,
        product_id,
    )

    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    update_data = product_data.model_dump(
        exclude_unset=True
    )

    if "category_id" in update_data:
        category = db.get(
            Category,
            update_data["category_id"],
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product(
    product_id: int,
    user_id: CurrentUserId,
    db: DbSession,
):
    product = db.get(
        Product,
        product_id,
    )

    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Soft delete: preserve product and order history.
    product.is_active = False

    db.commit()

    return None


# ==================================================
# INTERNAL SERVICE AUTHENTICATION
# ==================================================

def verify_internal_service(
    internal_secret: str = Header(
        ...,
        alias="X-Internal-Secret",
    ),
) -> None:

    expected_secret = os.getenv(
        "INTERNAL_SERVICE_SECRET"
    )

    if (
        not expected_secret
        or not secrets.compare_digest(
            internal_secret,
            expected_secret,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal service credentials",
        )


# ==================================================
# STOCK RESERVATION
# ==================================================

@router.post(
    "/internal/products/{product_id}/reserve",
)
def reserve_product_stock(
    product_id: int,
    request: StockQuantityRequest,
    db: DbSession,
    _: None = Depends(verify_internal_service),
):
    # Atomically reduce stock only when sufficient
    # stock is available and the product is active.

    result = db.execute(
        update(Product)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Product.stock_quantity >= request.quantity,
        )
        .values(
            stock_quantity=(
                Product.stock_quantity - request.quantity
            )
        )
    )

    if result.rowcount == 0:
        db.rollback()

        product = db.get(
            Product,
            product_id,
        )

        if product is None or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient stock",
        )

    db.commit()

    product = db.get(
        Product,
        product_id,
    )

    return {
        "message": "Stock reserved successfully",
        "product_id": product_id,
        "reserved_quantity": request.quantity,
        "remaining_stock": product.stock_quantity,
    }


# ==================================================
# RELEASE RESERVED STOCK
# ==================================================

@router.post(
    "/internal/products/{product_id}/release",
)
def release_product_stock(
    product_id: int,
    request: StockQuantityRequest,
    db: DbSession,
    _: None = Depends(verify_internal_service),
):
    # Restore previously reserved stock.
    # This also works for inactive products.

    result = db.execute(
        update(Product)
        .where(
            Product.id == product_id,
        )
        .values(
            stock_quantity=(
                Product.stock_quantity + request.quantity
            )
        )
    )

    if result.rowcount == 0:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    db.commit()

    product = db.get(
        Product,
        product_id,
    )

    return {
        "message": "Stock released successfully",
        "product_id": product_id,
        "released_quantity": request.quantity,
        "remaining_stock": product.stock_quantity,
    }
