import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CharacterProfile(Base):
    __tablename__ = "character_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    build_stage: Mapped[str] = mapped_column(String(50), default="early_endgame")
    character_level: Mapped[int | None]
    life: Mapped[int | None]
    energy_shield: Mapped[int | None]
    mana: Mapped[int | None]
    spirit: Mapped[int | None]
    spirit_required: Mapped[int | None]
    spirit_reserved: Mapped[int | None]
    strength: Mapped[int | None]
    dexterity: Mapped[int | None]
    intelligence: Mapped[int | None]
    fire_resistance: Mapped[int | None]
    cold_resistance: Mapped[int | None]
    lightning_resistance: Mapped[int | None]
    chaos_resistance: Mapped[int | None]
    resistance_cap: Mapped[int] = mapped_column(default=75)
    notes: Mapped[str] = mapped_column(Text, default="")


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_text: Mapped[str] = mapped_column(Text)
    unknown_lines: Mapped[list[str]] = mapped_column(JSON, default=list)
    item_class: Mapped[str | None] = mapped_column(String(100))
    rarity: Mapped[str | None] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column(String(200))
    base_type: Mapped[str | None] = mapped_column(String(200))
    required_level: Mapped[int | None]
    required_strength: Mapped[int | None]
    required_dexterity: Mapped[int | None]
    required_intelligence: Mapped[int | None]
    item_level: Mapped[int | None]
    quality: Mapped[int | None]
    sockets: Mapped[list[str]] = mapped_column(JSON, default=list)
    armour: Mapped[int | None]
    armour_augmented: Mapped[bool] = mapped_column(default=False)
    evasion: Mapped[int | None]
    evasion_augmented: Mapped[bool] = mapped_column(default=False)
    energy_shield: Mapped[int | None]
    energy_shield_augmented: Mapped[bool] = mapped_column(default=False)
    spirit: Mapped[int | None]
    granted_skill: Mapped[str | None] = mapped_column(String(300))
    identified: Mapped[bool] = mapped_column(Boolean, default=True)
    corrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    modifiers: Mapped[list["Modifier"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class Modifier(Base):
    __tablename__ = "modifiers"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(30))
    affix_type: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(200))
    tier: Mapped[int | None]
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_key: Mapped[str] = mapped_column(String(100), default="unknown")
    values: Mapped[list[float]] = mapped_column(JSON, default=list)
    roll_ranges: Mapped[list[list[float]]] = mapped_column(JSON, default=list)
    crafted: Mapped[bool] = mapped_column(default=False)
    desecrated: Mapped[bool] = mapped_column(default=False)
    rune: Mapped[bool] = mapped_column(default=False)
    implicit: Mapped[bool] = mapped_column(default=False)
    unique: Mapped[bool] = mapped_column(default=False)
    item: Mapped[Item] = relationship(back_populates="modifiers")


class EquipmentSlot(Base):
    __tablename__ = "equipment_slots"
    character_id: Mapped[int] = mapped_column(ForeignKey("character_profiles.id"), primary_key=True)
    slot: Mapped[str] = mapped_column(String(30), primary_key=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id"), unique=True)


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character_profiles.id"), index=True)
    target_slot: Mapped[str | None] = mapped_column(String(30))
    build_fit_score: Mapped[int | None]
    equipped_item_score: Mapped[int | None]
    score_delta: Mapped[int | None]
    upgrade_recommendation: Mapped[str | None] = mapped_column(String(50))
    trade_potential_score: Mapped[int | None]
    trade_recommendation: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[str | None] = mapped_column(String(20))
    completeness: Mapped[str | None] = mapped_column(String(20))
    rule_version: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(20), default="checked")
    local_category: Mapped[str | None] = mapped_column(String(50))
    local_delta_band: Mapped[str | None] = mapped_column(String(30))
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    parent_evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluations.id", ondelete="SET NULL"), index=True,
    )
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SaleRecord(Base):
    __tablename__ = "sale_records"
    __table_args__ = (UniqueConstraint("item_id", name="uq_sale_records_item_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    listed_currency: Mapped[str | None] = mapped_column(String(50))
    listed_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sold_currency: Mapped[str | None] = mapped_column(String(50))
    sold_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(30), default="listed")
    notes: Mapped[str] = mapped_column(Text, default="")
