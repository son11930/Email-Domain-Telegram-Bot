"""Database schema. All monetary amounts use exact integer units (1e8/USDT)."""
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(UTC)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    __table_args__ = (CheckConstraint('balance_units >= 0'),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(256), default='')
    balance_units: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Email(Base):
    __tablename__ = 'email_inventory'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='available', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    request_key: Mapped[str] = mapped_column(String(160), unique=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price_units: Mapped[int] = mapped_column(BigInteger)
    total_units: Mapped[int] = mapped_column(BigInteger)
    balance_units: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index('ix_orders_status_delivered_at', 'status', 'delivered_at'),)

class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), index=True)
    email_id: Mapped[int] = mapped_column(ForeignKey('email_inventory.id'), unique=True)

class Ledger(Base):
    __tablename__ = 'wallet_ledger'
    __table_args__ = (CheckConstraint('after_units >= 0'),
                      Index('ix_wallet_ledger_created_at_reference', 'created_at', 'reference'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    delta_units: Mapped[int] = mapped_column(BigInteger)
    before_units: Mapped[int] = mapped_column(BigInteger)
    after_units: Mapped[int] = mapped_column(BigInteger)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reason: Mapped[str] = mapped_column(String(500))
    reference: Mapped[str] = mapped_column(String(300), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Topup(Base):
    __tablename__ = 'topup_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    base_units: Mapped[int] = mapped_column(BigInteger)
    expected_units: Mapped[int] = mapped_column(BigInteger, unique=True)
    status: Mapped[str] = mapped_column(String(24), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class AmountLease(Base):
    __tablename__ = 'amount_leases'
    amount_units: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    topup_id: Mapped[str] = mapped_column(String(36), unique=True)

class Payment(Base):
    __tablename__ = 'payment_events'
    __table_args__ = (Index('ix_payment_events_status_occurred_at', 'status', 'occurred_at'),)
    transaction_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    amount_units: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(20))
    receiver_id: Mapped[str] = mapped_column(String(160), default='')
    order_type: Mapped[str] = mapped_column(String(30), default='')
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))
    topup_id: Mapped[str | None] = mapped_column(ForeignKey('topup_requests.id'), nullable=True)

class BankTopup(Base):
    __tablename__ = 'bank_topup_requests'
    __table_args__ = (CheckConstraint('base_satang >= 15000'),
                      CheckConstraint('expected_satang > base_satang'),
                      CheckConstraint('credited_units > 0'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    base_satang: Mapped[int] = mapped_column(BigInteger)
    expected_satang: Mapped[int] = mapped_column(BigInteger, unique=True)
    credited_units: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class BankPayment(Base):
    __tablename__ = 'bank_payment_events'
    __table_args__ = (CheckConstraint('amount_satang > 0'),
                      Index('ix_bank_payment_events_status_occurred_at', 'status', 'occurred_at'))
    trans_ref: Mapped[str] = mapped_column(String(256), primary_key=True)
    topup_id: Mapped[str] = mapped_column(ForeignKey('bank_topup_requests.id'), index=True)
    amount_satang: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))

class SlipVerificationAttempt(Base):
    __tablename__ = 'slip_verification_attempts'
    __table_args__ = (CheckConstraint('slot BETWEEN 1 AND 5'),)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    bangkok_date: Mapped[date] = mapped_column(Date, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Outbox(Base):
    __tablename__ = 'delivery_outbox'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str] = mapped_column(String(300), default='')
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)

class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Checkpoint(Base):
    __tablename__ = 'payment_checkpoints'
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Setting(Base):
    __tablename__ = 'settings'
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger)
