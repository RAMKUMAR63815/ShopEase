from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payment_order_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(Integer, nullable=False, index=True)

    user_id = Column(Integer, nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
    )

    payment_method = Column(
        String(30),
        nullable=False,
        default="SIMULATED",
    )

    transaction_reference = Column(
        String(100),
        nullable=True,
        unique=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )