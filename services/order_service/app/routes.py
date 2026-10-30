import os
from decimal import Decimal
from typing import Annotated
from app.schemas import OrderPaymentUpdate
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Order, OrderItem
from app.schemas import OrderCreate, OrderResponse
from app.security import CurrentUserId


router = APIRouter(prefix="/orders", tags=["Orders"])

DbSession = Annotated[Session, Depends(get_db)]

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL","http://product_service:8007")


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED
)
def create_order(
    order_data: OrderCreate,
    user_id: CurrentUserId,
    db: DbSession
):
    total_amount = Decimal("0.00")
    order_items = []

    # Use a bounded timeout for communication with Product Service.
    try:
        with httpx.Client(timeout=5.0) as client: #httpx is a Python library used to send HTTP requests to other services or APIs.
        #Using this client, you can send multiple requests:
            for requested_item in order_data.items:
                response = client.get(f"{PRODUCT_SERVICE_URL}/products/"f"{requested_item.product_id}")

                if response.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Product {requested_item.product_id} "
                            "was not found"
                        )
                    )

                response.raise_for_status()
                product = response.json()

                if requested_item.quantity > product["stock_quantity"]:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Insufficient stock for "
                            f"{product['name']}"
                        )
                    )

                unit_price = Decimal(str(product["price"]))
                line_total = unit_price * requested_item.quantity

                total_amount += line_total

                order_items.append(
                    OrderItem(
                        product_id=product["id"],
                        product_name=product["name"],
                        unit_price=unit_price,
                        quantity=requested_item.quantity,
                        line_total=line_total
                    )
                )

    except HTTPException:
        raise

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="Product Service returned an error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Product Service is currently unavailable"
        )

    order = Order(
        user_id=user_id,
        total_amount=total_amount,
        status="PENDING",
        items=order_items
    )

    try:
        db.add(order)
        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create order"
        )

    return db.scalar(
        select(Order)#.options() → Specify additional loading instructions.
        .options(selectinload(Order.items)) # one order has multiple order item ##When I fetch an Order, also fetch its related items using a separate SQL query
        .where(Order.id == order.id) # this cause N+1 prblem need additonal 100 query
    )


@router.get("", response_model=list[OrderResponse])
def get_my_orders(
    user_id: CurrentUserId,
    db: DbSession
):
    return db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    ).all()


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    user_id: CurrentUserId,
    db: DbSession
):
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.id == order_id,
            Order.user_id == user_id
        )
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return order

@router.patch("/{order_id}/payment-status")
def update_order_payment_status(
    order_id: int,
    request: OrderPaymentUpdate,
    db: Session = Depends(get_db),
    internal_secret: str = Header(..., alias="X-Internal-Secret"),
):
    expected_secret = os.getenv("INTERNAL_SERVICE_SECRET")

    if not expected_secret or internal_secret != expected_secret:
        raise HTTPException(
            status_code=403,
            detail="Invalid internal service credentials",
        )

    order = db.get(Order, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if order.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Order is not awaiting payment",
        )

    order.status = request.status

    db.commit()
    db.refresh(order)

    return {
        "message": "Order payment status updated",
        "order_id": order.id,
        "status": order.status,
    }