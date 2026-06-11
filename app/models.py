from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Talent(Base):
    __tablename__ = "talents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)  # D-13
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # D-13
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # D-13 (niche)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    products: Mapped[list["TalentProduct"]] = relationship(
        back_populates="talent", cascade="all, delete-orphan"
    )


class TalentProduct(Base):
    __tablename__ = "talent_products"  # D-14

    id: Mapped[int] = mapped_column(primary_key=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)
    pipedrive_product_id: Mapped[int | None] = mapped_column(nullable=True)  # D-15: null in Phase 1

    talent: Mapped["Talent"] = relationship(back_populates="products")
