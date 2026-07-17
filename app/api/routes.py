from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluateItemRequest, EvaluateItemResponse, EvaluationInput
from app.evaluation.service import get_evaluation_provider
from app.builds.registry import BuildContext, get_build, list_builds
from app.db.session import SessionLocal
from app.db.models import CharacterProfile, EquipmentSlot, Item
from app.equipment.service import (
    SLOT_CLASSES, equipment_response, export_equipment, get_or_create_profile, import_equipment,
    profile_schema, put_profile, replace_equipment,
)

from app.parser.service import parse_with_warnings
from app.schemas.health import HealthResponse
from app.schemas.parsing import ParseItemRequest, ParseItemResponse
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


@router.get("/builds", response_model=list[BuildContext])
async def get_builds() -> tuple[BuildContext, ...]:
    return list_builds()


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
    if parsed.item.item_class != SLOT_CLASSES[request.target_slot]:
        raise HTTPException(status_code=422, detail={
            "code": "item_slot_mismatch",
            "message": "Die Item Class passt nicht zum gewählten Zielslot.",
        })
    try:
        build = get_build(request.build_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "unknown_build", "message": "Der gewählte Build ist nicht verfügbar."
        }) from exc
    from app.equipment.service import item_schema, profile_schema
    row = db.get(EquipmentSlot, (1, request.target_slot))
    equipped_orm = db.get(Item, row.item_id) if row and row.item_id else None
    equipped = item_schema(equipped_orm) if equipped_orm else None
    if equipped is None:
        raise HTTPException(status_code=422, detail={
            "code": "equipped_item_required",
            "message": "Im gewählten Zielslot muss zuerst ein Item ausgerüstet werden.",
        })
    profile = db.get(CharacterProfile, 1) if request.use_profile else None
    evaluation_input = EvaluationInput(
        candidate=parsed.item,
        equipped=equipped,
        target_slot=request.target_slot,
        observed_profile=profile_schema(profile) if profile else None,
        build=build,
    )
    try:
        provider = get_evaluation_provider()
        evaluation = await provider.evaluate(evaluation_input)
    except EvaluationProviderError as exc:
        return EvaluateItemResponse(
            parse=parsed, build=build, target_slot=request.target_slot, equipped=equipped,
            evaluation=None,
            provider=None, model=None, provider_status="unavailable",
            provider_error={"code": exc.code, "message": exc.public_message},
            disclaimer=("API-Empfehlung nicht verfügbar. Es wurde keine lokale Empfehlung "
                        "oder Ersatzbewertung erzeugt."),
        )
    return EvaluateItemResponse(
        parse=parsed, build=build, target_slot=request.target_slot, equipped=equipped,
        evaluation=evaluation,
        provider=provider.name, model=provider.model, provider_status="success",
        provider_error=None,
        disclaimer=("API-gestützter Candidate-vs-Equipped-Vergleich. Keine Marktwert- oder "
                    "Crafting-Bewertung."),
    )
