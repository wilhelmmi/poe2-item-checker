from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.buildfit.engine import compare_slots
from app.db.models import CharacterProfile, EquipmentSlot, Evaluation, Item, Modifier, SaleRecord
from app.equipment.service import SLOT_CLASSES, get_or_create_profile, item_schema, profile_schema, store_item
from app.facts.engine import check_item_facts
from app.history.schemas import (
    BackupEvaluation, BackupItem, BackupSale, FullBackup, HistoryEntry, HistoryPage,
    HistoryUpdate, SaleData, SaveEvaluationRequest,
)
from app.parser.service import parse_with_warnings
from app.schemas.management import SLOTS

BLOCKING = {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"}


def _equipment(db: Session) -> tuple[dict, set[str]]:
    rows = db.scalars(select(EquipmentSlot).where(EquipmentSlot.character_id == 1)).all()
    known = {row.slot for row in rows}
    equipment = {}
    for row in rows:
        item = db.get(Item, row.item_id) if row.item_id else None
        equipment[row.slot] = item_schema(item) if item else None
    return equipment, known


def _targets(item_class: str | None, requested: str | None) -> list[str]:
    if requested:
        return [requested]
    if item_class == "Rings":
        return ["ring_1", "ring_2"]
    return [slot for slot, slot_class in SLOT_CLASSES.items() if slot_class == item_class]


def save_local_evaluation(
    db: Session, request: SaveEvaluationRequest, parent_id: str | None = None,
    existing_item: Item | None = None, status: str = "checked",
) -> Evaluation:
    parsed = parse_with_warnings(request.raw_text)
    if any(warning.code in BLOCKING for warning in parsed.warnings):
        raise ValueError("incomplete_item")
    if request.target_slot and parsed.item.item_class != SLOT_CLASSES[request.target_slot]:
        raise ValueError("item_slot_mismatch")
    profile = get_or_create_profile(db)
    equipment, known = _equipment(db)
    comparison = compare_slots(
        parsed.item, _targets(parsed.item.item_class, request.target_slot), equipment, known,
        profile if request.use_profile else None,
    )
    target = request.target_slot or comparison.recommended_target
    selected = next((entry for entry in comparison.comparisons if entry.target_slot == target), None)
    if selected is None:
        raise ValueError("no_compatible_slot")
    local_check = check_item_facts(parsed.item)
    item = existing_item or store_item(db, parsed.item)
    now = datetime.now(timezone.utc)
    evaluation = Evaluation(
        item_id=item.id, character_id=profile.id, target_slot=selected.target_slot,
        build_fit_score=selected.candidate.score,
        equipped_item_score=selected.equipped.score if selected.equipped else None,
        score_delta=selected.delta, upgrade_recommendation=selected.category,
        confidence=selected.candidate.confidence, completeness=selected.candidate.completeness,
        rule_version=selected.candidate.rule_version, status=status,
        local_category=selected.category, local_delta_band=selected.delta_band,
        snapshot={
            "parse_warnings": [warning.model_dump(mode="json") for warning in parsed.warnings],
            "local_check": local_check.model_dump(mode="json"),
            "local_comparison": comparison.model_dump(mode="json"),
            "selected_comparison": selected.model_dump(mode="json"),
            "provider": None,
        },
        parent_evaluation_id=parent_id, reasons=[], warnings=selected.warnings,
        created_at=now, updated_at=now,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def _sale_data(sale: SaleRecord | None) -> SaleData | None:
    if sale is None:
        return None
    values = {field: getattr(sale, field) for field in SaleData.model_fields}
    for field in ("listed_at", "sold_at"):
        if values[field] and values[field].tzinfo is None:
            values[field] = values[field].replace(tzinfo=timezone.utc)
    return SaleData.model_validate(values)


def entry_schema(db: Session, evaluation: Evaluation) -> HistoryEntry:
    item = db.get(Item, evaluation.item_id)
    sale = db.scalar(select(SaleRecord).where(SaleRecord.item_id == evaluation.item_id).order_by(SaleRecord.id.desc()))
    return HistoryEntry(
        id=evaluation.id, item_id=evaluation.item_id, parent_evaluation_id=evaluation.parent_evaluation_id,
        target_slot=evaluation.target_slot, status=evaluation.status,
        category=evaluation.local_category or evaluation.upgrade_recommendation or "unknown",
        delta_band=evaluation.local_delta_band, candidate_score=evaluation.build_fit_score or 0,
        equipped_score=evaluation.equipped_item_score, delta=evaluation.score_delta,
        confidence=evaluation.confidence or "low", completeness=evaluation.completeness or "partial",
        rule_version=evaluation.rule_version or 1, created_at=evaluation.created_at,
        updated_at=evaluation.updated_at, item=item_schema(item), sale=_sale_data(sale),
        snapshot=evaluation.snapshot or {},
    )


def list_history(db: Session, *, slot: str | None, category: str | None, status: str | None,
                 base_type: str | None, rarity: str | None, date_from: datetime | None,
                 date_to: datetime | None, limit: int, offset: int) -> HistoryPage:
    query = select(Evaluation).join(Item, Evaluation.item_id == Item.id)
    filters = []
    if slot:
        filters.append(Evaluation.target_slot == slot)
    if category:
        filters.append(Evaluation.local_category == category)
    if status:
        filters.append(Evaluation.status == status)
    if base_type:
        filters.append(Item.base_type.ilike(f"%{base_type}%"))
    if rarity:
        filters.append(Item.rarity == rarity)
    if date_from:
        filters.append(Evaluation.created_at >= date_from)
    if date_to:
        filters.append(Evaluation.created_at <= date_to)
    query = query.where(*filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Evaluation.created_at.desc(), Evaluation.id.desc()).limit(limit).offset(offset)).all()
    return HistoryPage(items=[entry_schema(db, row) for row in rows], total=total, limit=limit, offset=offset)


def update_history(db: Session, evaluation: Evaluation, data: HistoryUpdate) -> HistoryEntry:
    now = datetime.now(timezone.utc)
    db.query(Evaluation).filter(Evaluation.item_id == evaluation.item_id).update(
        {Evaluation.status: data.status, Evaluation.updated_at: now}, synchronize_session="fetch",
    )
    sale = db.scalar(select(SaleRecord).where(SaleRecord.item_id == evaluation.item_id).order_by(SaleRecord.id.desc()))
    supplied_sale = any(getattr(data, field) is not None for field in (
        "listed_at", "listed_currency", "listed_amount", "sold_at", "sold_currency", "sold_amount"
    )) or bool(data.notes)
    if sale is None and supplied_sale:
        sale = SaleRecord(item_id=evaluation.item_id)
        db.add(sale)
    if sale:
        for field in SaleData.model_fields:
            setattr(sale, field, getattr(data, field))
        sale.status = data.status
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("sale_record_conflict") from exc
    return entry_schema(db, evaluation)


def create_backup(db: Session) -> FullBackup:
    profile = get_or_create_profile(db)
    db.flush()
    items = db.scalars(select(Item).order_by(Item.created_at, Item.id)).all()
    evaluations = db.scalars(select(Evaluation).order_by(Evaluation.created_at, Evaluation.id)).all()
    sales = db.scalars(select(SaleRecord).order_by(SaleRecord.id)).all()
    slots = {row.slot: row.item_id for row in db.scalars(select(EquipmentSlot).where(EquipmentSlot.character_id == 1))}
    return FullBackup(
        profile=profile_schema(profile), equipment={slot: slots.get(slot) for slot in SLOTS},
        items=[BackupItem(id=item.id, created_at=item.created_at, item=item_schema(item)) for item in items],
        evaluations=[BackupEvaluation.model_validate({field: getattr(row, field) for field in BackupEvaluation.model_fields}) for row in evaluations],
        sales=[BackupSale.model_validate({
            field: (_sale_data(row).model_dump()[field] if field in SaleData.model_fields else getattr(row, field))
            for field in BackupSale.model_fields
        }) for row in sales],
    )


def restore_backup(db: Session, backup: FullBackup) -> None:
    # Pydantic has fully validated structure and references before this transaction starts.
    try:
        db.query(SaleRecord).delete()
        db.query(Evaluation).delete()
        db.query(EquipmentSlot).delete()
        db.query(Modifier).delete()
        db.query(Item).delete()
        db.query(CharacterProfile).delete()
        profile = CharacterProfile(id=1, **backup.profile.model_dump())
        db.add(profile)
        for source in backup.items:
            values = source.item.model_dump(exclude={"modifiers"})
            item = Item(id=source.id, created_at=source.created_at, **values)
            item.modifiers = [Modifier(**modifier.model_dump()) for modifier in source.item.modifiers]
            db.add(item)
        db.flush()
        for slot, item_id in backup.equipment.items():
            db.add(EquipmentSlot(character_id=1, slot=slot, item_id=item_id))
        db.flush()
        pending = list(backup.evaluations)
        inserted: set[str] = set()
        while pending:
            ready = [row for row in pending if row.parent_evaluation_id is None or row.parent_evaluation_id in inserted]
            if not ready:
                raise ValueError("cyclic evaluation lineage")
            for source in ready:
                db.add(Evaluation(**source.model_dump()))
                inserted.add(source.id)
                pending.remove(source)
            db.flush()
        for source in backup.sales:
            db.add(SaleRecord(**source.model_dump()))
        db.commit()
    except Exception:
        db.rollback()
        raise
