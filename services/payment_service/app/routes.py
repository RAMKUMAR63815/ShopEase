import os
import uuid

import httpx

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment
from app.schemas import PaymentCreate, PaymentResponse
from app.security import get_current_user_id


router = APIRouter(prefix="/payments", tags=["Payments"])

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL","http://order_service:8004",)
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET")

@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    request: PaymentCreate,
    authorization: str = Header(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Check whether this order already has a payment.
    existing_payment = db.scalar(
        select(Payment).where(
            Payment.order_id == request.order_id
        )
    )

    if existing_payment:
        if existing_payment.user_id != user_id:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        return existing_payment

    # Ask Order Service for the actual order details.
    try:
        response = httpx.get(
            f"{ORDER_SERVICE_URL}/orders/{request.order_id}",
            headers={"Authorization": authorization},
            timeout=5.0,
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Order authorization failed",
            )

        response.raise_for_status()
        order_data = response.json()

    except HTTPException:
        raise

    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Order Service is unavailable",
        )

    # Read the real amount from the Order Service.
    amount = order_data.get("total_amount")

    if amount is None:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Order Service",
        )

    # Simulate a successful payment.
    payment = Payment(
        order_id=request.order_id,
        user_id=user_id,
        amount=amount,
        status="SUCCESS",
        payment_method="SIMULATED",
        transaction_reference=f"SIM-{uuid.uuid4().hex[:12].upper()}",
    )

    try:
        db.add(payment)
        db.commit()
        db.refresh(payment)

    except IntegrityError:
        db.rollback()

        # Another request may have created the payment simultaneously.
        existing_payment = db.scalar(
            select(Payment).where(
                Payment.order_id == request.order_id
            )
        )

        if existing_payment and existing_payment.user_id == user_id:
            return existing_payment

        raise HTTPException(
            status_code=409,
            detail="Payment already exists for this order",
        )

    # Notify Order Service that payment succeeded.
    try:
        order_update_response = httpx.patch(
            f"{ORDER_SERVICE_URL}/orders/{request.order_id}/payment-status",
            json={"status": "PAID"},
            headers={
                "X-Internal-Secret": INTERNAL_SERVICE_SECRET
            },
            timeout=5.0,
        )

        order_update_response.raise_for_status()

    except httpx.HTTPError:
        # Payment succeeded, but order status update failed.
        # Do not pretend the complete workflow succeeded.
        raise HTTPException(
            status_code=502,
            detail=(
                "Payment succeeded, but order status update failed. "
                "Payment requires reconciliation."
            ),
        )

    return payment


@router.get(
    "/",
    response_model=list[PaymentResponse],
)
def get_my_payments(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    payments = db.scalars(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
    ).all()

    return payments


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment(
    payment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    payment = db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.user_id == user_id,
        )
    )

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    return payment