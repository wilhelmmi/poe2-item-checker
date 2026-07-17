from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluateItemRequest, EvaluateItemResponse
from app.evaluation.service import get_evaluation_provider
from app.db.session import SessionLocal
from app.comparison.engine import compare_hard_checks
from app.buildfit.engine import compare_slots
from app.db.models import CharacterProfile, EquipmentSlot, Evaluation, Item
from app.history.schemas import (
    FullBackup, HistoryCategory, HistoryEntry, HistoryPage, HistoryStatus, HistoryUpdate,
    SaveEvaluationRequest,
)
from app.history.service import (
    create_backup, entry_schema, list_history, restore_backup, save_local_evaluation, update_history,
)
from app.equipment.service import (
    SLOT_CLASSES, equipment_response, export_equipment, get_or_create_profile, import_equipment,
    profile_schema, put_profile, replace_equipment,
)

from app.facts.engine import check_item_facts
from app.parser.service import parse_with_warnings
from app.schemas.checking import CheckItemResponse
from app.schemas.health import HealthResponse
from app.schemas.parsing import ParseItemRequest, ParseItemResponse, ParseWarning
from app.schemas.management import (
    EquipmentExport, EquipmentImportData, EquipmentItem, EquipmentPut, EquipmentResponse,
    ProfileData, Slot,
)

router = APIRouter(prefix="/api")


async def database() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/profile", response_model=ProfileData)
async def get_profile(db: Session = Depends(database)) -> ProfileData:
    profile = get_or_create_profile(db)
    db.commit()
    return profile_schema(profile)


@router.put("/profile", response_model=ProfileData)
async def update_profile(data: ProfileData, db: Session = Depends(database)) -> ProfileData:
    return put_profile(db, data)


@router.get("/equipment", response_model=EquipmentResponse)
async def get_equipment(db: Session = Depends(database)) -> EquipmentResponse:
    return equipment_response(db)


@router.put("/equipment/{slot}", response_model=EquipmentItem)
async def put_equipment(slot: Slot, data: EquipmentPut, db: Session = Depends(database)) -> EquipmentItem:
    try:
        return replace_equipment(db, slot, data.raw_text)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/equipment/import", response_model=EquipmentResponse)
async def import_equipment_seed(data: EquipmentImportData, db: Session = Depends(database)) -> EquipmentResponse:
    try:
        return import_equipment(db, data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.get("/equipment/export", response_model=EquipmentExport)
async def get_equipment_export(db: Session = Depends(database)) -> EquipmentExport:
    return export_equipment(db)


@router.post("/items/parse", response_model=ParseItemResponse)
async def parse_item(request: ParseItemRequest) -> ParseItemResponse:
    return parse_with_warnings(request.raw_text)


@router.post("/items/check", response_model=CheckItemResponse)
async def check_item(request: ParseItemRequest) -> CheckItemResponse:
    parsed = parse_with_warnings(request.raw_text)
    blocking_codes = {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"}
    if any(warning.code in blocking_codes for warning in parsed.warnings):
        parsed.warnings.append(ParseWarning(
            code="assessment_skipped",
            message="Der lokale Faktencheck wurde wegen unvollständiger Parserdaten übersprungen.",
            lines=[],
            raw_lines=[],
        ))
        return CheckItemResponse(parse=parsed, assessment=None)
    return CheckItemResponse(parse=parsed, assessment=check_item_facts(parsed.item))


@router.post("/items/evaluate", response_model=EvaluateItemResponse)
async def evaluate_item(
    request: EvaluateItemRequest, db: Session = Depends(database),
) -> EvaluateItemResponse:
    parsed = parse_with_warnings(request.raw_text)
    blocking_codes = {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"}
    if any(warning.code in blocking_codes for warning in parsed.warnings):
        raise HTTPException(
            status_code=422,
            detail={"code": "incomplete_item", "message": "Der Itemtext ist nicht vollständig analysierbar."},
        )
    local_check = check_item_facts(parsed.item)
    if request.target_slot and parsed.item.item_class != SLOT_CLASSES[request.target_slot]:
        raise HTTPException(status_code=422, detail={
            "code": "item_slot_mismatch",
            "message": "Die Item Class passt nicht zum gewählten Zielslot.",
        })
    from app.equipment.service import item_schema
    rows = db.query(EquipmentSlot).filter_by(character_id=1).all()
    known_slots = {row.slot for row in rows}
    equipment = {}
    for row in rows:
        equipped_orm = db.get(Item, row.item_id) if row.item_id else None
        equipment[row.slot] = item_schema(equipped_orm) if equipped_orm else None
    profile = db.get(CharacterProfile, 1) if request.use_profile else None
    if request.target_slot:
        targets = [request.target_slot]
    elif parsed.item.item_class == "Rings":
        targets = ["ring_1", "ring_2"]
    else:
        targets = [slot for slot, item_class in SLOT_CLASSES.items() if item_class == parsed.item.item_class]
    local_comparison = compare_slots(parsed.item, targets, equipment, known_slots, profile)
    hard_checks = (
        local_comparison.comparisons[0].hard_checks if local_comparison.comparisons
        else compare_hard_checks(parsed.item, None, profile, None)
    )
    try:
        provider = get_evaluation_provider()
        evaluation = await provider.evaluate(local_check.facts)
    except EvaluationProviderError as exc:
        return EvaluateItemResponse(
            parse=parsed, local_check=local_check, evaluation=None,
            provider=None, model=None, provider_status="unavailable",
            provider_error={"code": exc.code, "message": exc.public_message},
            hard_checks=hard_checks,
            local_comparison=local_comparison,
            disclaimer=("AI-Bewertung nicht verfügbar; der lokale Faktencheck wurde als "
                        "sicherer Fallback ausgeführt."),
        )
    return EvaluateItemResponse(
        parse=parsed, local_check=local_check, evaluation=evaluation,
        provider=provider.name, model=provider.model, provider_status="success",
        provider_error=None,
        hard_checks=hard_checks,
        local_comparison=local_comparison,
        disclaimer=("AI-gestützte Einschätzung ohne garantierte Live-Marktpreise; der lokale "
                    "Faktencheck bleibt als Guardrail erhalten."),
    )


@router.post("/history", response_model=HistoryEntry, status_code=201)
async def persist_evaluation(
    request: SaveEvaluationRequest, db: Session = Depends(database),
) -> HistoryEntry:
    try:
        return entry_schema(db, save_local_evaluation(db, request))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.get("/history", response_model=HistoryPage)
async def get_history(
    slot: Slot | None = None, category: HistoryCategory | None = None,
    status: HistoryStatus | None = None, base_type: str | None = Query(default=None, max_length=200),
    rarity: str | None = Query(default=None, max_length=30), date_from: datetime | None = None,
    date_to: datetime | None = None, limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0), db: Session = Depends(database),
) -> HistoryPage:
    return list_history(db, slot=slot, category=category, status=status, base_type=base_type,
                        rarity=rarity, date_from=date_from, date_to=date_to, limit=limit, offset=offset)


@router.get("/history/{evaluation_id}", response_model=HistoryEntry)
async def get_history_entry(evaluation_id: str, db: Session = Depends(database)) -> HistoryEntry:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail={"code": "history_not_found"})
    return entry_schema(db, evaluation)


@router.put("/history/{evaluation_id}", response_model=HistoryEntry)
async def put_history_entry(
    evaluation_id: str, data: HistoryUpdate, db: Session = Depends(database),
) -> HistoryEntry:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail={"code": "history_not_found"})
    try:
        return update_history(db, evaluation, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/history/{evaluation_id}/recompare", response_model=HistoryEntry, status_code=201)
async def recompare_history(evaluation_id: str, db: Session = Depends(database)) -> HistoryEntry:
    previous = db.get(Evaluation, evaluation_id)
    if previous is None:
        raise HTTPException(status_code=404, detail={"code": "history_not_found"})
    item = db.get(Item, previous.item_id)
    try:
        current = save_local_evaluation(db, SaveEvaluationRequest(
            raw_text=item.raw_text, target_slot=previous.target_slot, use_profile=True,
        ), parent_id=previous.id, existing_item=item, status=previous.status)
        return entry_schema(db, current)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.get("/backup", response_model=FullBackup)
async def download_backup(db: Session = Depends(database)) -> FullBackup:
    backup = create_backup(db)
    db.commit()
    return backup


MAX_BACKUP_BYTES = 10_000_000


@router.post("/backup/restore", status_code=204)
async def upload_backup(request: Request, db: Session = Depends(database)) -> Response:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BACKUP_BYTES:
                raise HTTPException(status_code=413, detail={"code": "backup_too_large"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_content_length"}) from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BACKUP_BYTES:
            raise HTTPException(status_code=413, detail={"code": "backup_too_large"})
        body.extend(chunk)
    try:
        data = FullBackup.model_validate_json(bytes(body))
        restore_backup(db, data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_backup"}) from exc
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": "invalid_backup"}) from exc
    return Response(status_code=204)
