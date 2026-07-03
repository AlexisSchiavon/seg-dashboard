from datetime import date, datetime

from sqlalchemy import String, Text, Boolean, Float, Integer, ForeignKey, DateTime, Date, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
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
    stage_name: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)  # open/won/lost

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
    # 5.3: timestamp the deal became status='won' (Pipedrive v2 won_time).
    # Stored as timezone-aware UTC; convert to America/Mexico_City only at render.
    won_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class DealStageEvent(Base):
    __tablename__ = "deal_stage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_pipedrive_id: Mapped[int] = mapped_column(Integer, index=True)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True, index=True)
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

    # Fase 8 (8.1): full email body + classifier reason for the lead detail modal.
    # email_completo is plain text, sanitized with bleach at sync write-time (D4/D6/D9).
    # email_truncated marks bodies clipped at the 1 MB cap (D8). All nullable so old
    # rows synced before Fase 8 remain valid (D7 provides UI fallbacks).
    email_completo: Mapped[str | None] = mapped_column(Text, nullable=True)
    razon_validacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # categoria_detectada: classifier category label (e.g. "Moda/Retail"). Exists in
    # the live Sheet (Categoria_Detectada) — added to 8.1 once discovered via real sync.
    categoria_detectada: Mapped[str | None] = mapped_column(String, nullable=True)
    email_truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    talent: Mapped["Talent | None"] = relationship("Talent", lazy="select")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("talent_id", "month", name="uq_report_talent_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Fase 9.5: nullable for consolidated reports (talent_ids="all" / multi), which
    # have no single owning talent. Single-talent reports still set this.
    talent_id: Mapped[int | None] = mapped_column(
        ForeignKey("talents.id"), index=True, nullable=True
    )
    month: Mapped[str] = mapped_column(String, index=True)  # "YYYY-MM" / "YYYY-QN"
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Fase 9.5: PDFs are no longer persisted to disk — they are regenerated
    # on demand from this row's metadata. file_path is kept nullable for history.
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # Fase 9.5 metadata: the regenerate key ("all" or "10" or "10,11,12") and the
    # sha256 of the last-rendered PDF bytes (audit / change detection).
    talent_ids: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    talent: Mapped["Talent"] = relationship("Talent", lazy="select")


class TrelloCard(Base):
    __tablename__ = "trello_cards"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Natural key — Trello's immutable card ID (T-04-02: unique index prevents duplicate rows)
    trello_card_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    name: Mapped[str] = mapped_column(String)
    list_id: Mapped[str] = mapped_column(String)
    list_name: Mapped[str] = mapped_column(String)

    # Derived from LIST_STATE_MAP in trello.py:
    # ejecucion | cobranza | cerrado | omitido  (9.8a: 'omitido' = excluido de todo cálculo)
    list_state: Mapped[str] = mapped_column(String)

    # FK to deals.id (local PK, NOT deals.pipedrive_id) — nullable: card may predate sync
    deal_id: Mapped[int | None] = mapped_column(
        ForeignKey("deals.id"), nullable=True, index=True
    )

    # Pipedrive deal ID parsed from the card description "[seg:deal_id=N]" header
    pipedrive_deal_id_desc: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Trello card due date, used as collection_date; fallback = add_time + 2 months (TRELLO-02)
    collection_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
