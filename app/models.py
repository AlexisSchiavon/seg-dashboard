from datetime import datetime

from sqlalchemy import String, Boolean, Float, Integer, ForeignKey, DateTime, func
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


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipedrive_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String, default="MXN")
    stage_id: Mapped[int] = mapped_column(Integer)
    stage_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # open/won/lost

    # D-17: nullable, no cascade — "Sin talento asignado" deals must persist
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True, index=True)

    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    is_sin_cotizar: Mapped[bool] = mapped_column(Boolean, default=False)  # PIPE-03
    loss_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_category: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_collection_date: Mapped[str | None] = mapped_column(String, nullable=True)
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    update_time: Mapped[str] = mapped_column(String)  # for updated_since filter
    add_time: Mapped[str | None] = mapped_column(String, nullable=True)


class DealStageEvent(Base):
    __tablename__ = "deal_stage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_pipedrive_id: Mapped[int] = mapped_column(Integer, index=True)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True)
    from_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    to_stage: Mapped[str] = mapped_column(String)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, default="pipedrive")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String)  # running/success/error
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Natural key: sheet row number (header=row 1, first data row=2).
    # ID_Lead column is empty for all 730 live rows — do not use as key.
    # ASSUMPTION (A1): Sheet is append-only; row numbers are stable across syncs.
    sheet_row_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    remitente_email: Mapped[str] = mapped_column(String)
    remitente_nombre: Mapped[str] = mapped_column(String, default="")
    asunto: Mapped[str] = mapped_column(String, default="")
    fecha_recepcion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # D-32/D-33: nullable FK — None = "Sin talento asignado" bucket (mirrors Deal.talent_id)
    talent_id: Mapped[int | None] = mapped_column(
        ForeignKey("talents.id"), nullable=True, index=True
    )

    status_filtrado: Mapped[str] = mapped_column(String, index=True)
    fuente: Mapped[str] = mapped_column(String, default="Gmail")  # D-35: extensible for Phase 4
    score_calidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloqueado: Mapped[bool] = mapped_column(Boolean, default=False)
    convertido_a_prospecto: Mapped[bool] = mapped_column(Boolean, default=False)

    talent: Mapped["Talent | None"] = relationship("Talent", lazy="select")
