"""Database models and session management for structured grocery products."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class ProductRecord(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("platform", "product_id", name="uq_products_platform_product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    original_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="db")
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)


_engine = None
_session_maker: Optional[sessionmaker[Session]] = None


def _ensure_engine() -> None:
    global _engine, _session_maker
    if _engine is not None and _session_maker is not None:
        return
    settings = get_settings()
    _engine = create_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
    _session_maker = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def init_database() -> None:
    _ensure_engine()
    settings = get_settings()
    if settings.db_schema_auto_create:
        Base.metadata.create_all(bind=_engine)


def close_database() -> None:
    global _engine, _session_maker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_maker = None


def get_db_session() -> Session:
    _ensure_engine()
    assert _session_maker is not None
    return _session_maker()
