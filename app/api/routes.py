from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluateItemRequest, EvaluateItemResponse, EvaluationInput
from app.evaluation.service import get_evaluation_provider
from app.builds.registry import BuildContext
from app.builds.provider_service import get_build_provider
from app.builds.schemas import ActiveBuild, BuildPreviewRequest, BuildPreviewResponse
from app.builds.service import (canonicalize_source_url, confirm_preview, create_preview,
                                get_active, get_any_build, list_all_builds, row_context, set_active)
from app.db.session import SessionLocal
from app.db.models import CharacterProfile, EquipmentSlot, Item
from app.equipment.service import (
    SLOT_CLASSES,
    equipment_response,
    export_equipment,
    get_or_create_profile,
    import_equipment,
    profile_schema,
    put_profile,
    replace_equipment,
    equip_loadout,
)

from app.parser.service import (
    BLOCKING_WARNING_CODES,
    parse_with_safe_auto_format,
    parse_with_warnings,
)
from app.schemas.health import HealthResponse
from app.schemas.parsing import ParseItemRequest, ParseItemResponse
from app.schemas.items import ParsedItem
from app.schemas.management import (
    EquipmentExport,
    EquipmentImportData,
    EquipmentItem,
    EquipmentPut,
    EquipmentEquip,
    EquipmentResponse,
    ProfileData,
    Slot,
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
async def get_builds(db: Session = Depends(database)) -> tuple[BuildContext, ...]:
    return list_all_builds(db)


@router.get("/builds/active", response_model=ActiveBuild)
async def active_build(db: Session = Depends(database)) -> ActiveBuild:
    return ActiveBuild(build_id=get_active(db))


@router.put("/builds/active", response_model=ActiveBuild)
async def update_active_build(data: ActiveBuild, db: Session = Depends(database)) -> ActiveBuild:
    try:
        return ActiveBuild(build_id=set_active(db, data.build_id))
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "unknown_build", "message": "Der Build ist nicht verfügbar."}) from exc


@router.post("/builds/previews", response_model=BuildPreviewResponse)
async def analyze_build(data: BuildPreviewRequest, db: Session = Depends(database)) -> BuildPreviewResponse:
    try:
        source_url = canonicalize_source_url(data.source_url)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_build_url", "message": "Bitte eine öffentliche http(s)-Build-URL ohne Fragment eingeben."}) from exc
    try:
        provider = get_build_provider()
        analysis, citations = await provider.analyze(source_url)
    except EvaluationProviderError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.public_message}) from exc
    preview = create_preview(db, source_url, analysis, citations, provider.name, provider.model)
    return BuildPreviewResponse(preview_id=preview.id, source_url=preview.source_url,
        analysis=analysis, citations=citations, provider=preview.provider, model=preview.model,
        expires_at=preview.expires_at.isoformat())


@router.post("/builds/previews/{preview_id}/confirm", response_model=BuildContext)
async def confirm_build(preview_id: str, db: Session = Depends(database)) -> BuildContext:
    try:
        return row_context(confirm_preview(db, preview_id))
    except ValueError as exc:
        code = str(exc)
        status = 410 if code == "preview_expired" else 404 if code == "preview_not_found" else 409
        raise HTTPException(status, detail={"code": code, "message": "Die Build-Vorschau ist nicht mehr verfügbar."}) from exc


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
async def put_equipment(
    slot: Slot, data: EquipmentPut, db: Session = Depends(database)
) -> EquipmentItem:
    try:
        return replace_equipment(db, slot, data.raw_text)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/equipment/equip", response_model=EquipmentResponse)
async def equip_item(data: EquipmentEquip, db: Session = Depends(database)) -> EquipmentResponse:
    try:
        return equip_loadout(db, data.raw_text, data.ring_slot)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/equipment/import", response_model=EquipmentResponse)
async def import_equipment_seed(
    data: EquipmentImportData, db: Session = Depends(database)
) -> EquipmentResponse:
    try:
        return import_equipment(db, data)
    except ValueError as exc:
        db.rollback()
        code = str(exc)
        messages = {
            "item_slot_mismatch": "Mindestens ein Item passt nicht zu seinem Equipment-Slot.",
            "incomplete_item": "Mindestens ein Itemtext ist ungültig oder unvollständig.",
            "ambiguous_item_format": "Mindestens ein Itemtext ist nicht eindeutig formatiert.",
            "two_handed_slot_conflict": "Ein Staff muss im Wand-Slot stehen und benötigt einen leeren Fokus-Slot.",
        }
        raise HTTPException(
            status_code=422,
            detail={"code": code, "message": messages.get(code, "Der Equipmentimport ist ungültig.")},
        ) from exc


@router.get("/equipment/export", response_model=EquipmentExport)
async def get_equipment_export(db: Session = Depends(database)) -> EquipmentExport:
    return export_equipment(db)


@router.post("/items/parse", response_model=ParseItemResponse)
async def parse_item(request: ParseItemRequest) -> ParseItemResponse:
    return parse_with_warnings(request.raw_text)


@router.post("/items/evaluate", response_model=EvaluateItemResponse)
async def evaluate_item(
    request: EvaluateItemRequest,
    db: Session = Depends(database),
) -> EvaluateItemResponse:
    preflight = parse_with_warnings(request.raw_text)
    if preflight.auto_format_status == "ambiguous":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ambiguous_item_format",
                "message": (
                    "Der einzeilige Itemtext kann nicht sicher automatisch formatiert werden. "
                    "Bitte Zeilenumbrüche prüfen und manuell ergänzen."
                ),
            },
        )
    parsed = parse_with_safe_auto_format(request.raw_text)
    if any(warning.code in BLOCKING_WARNING_CODES for warning in parsed.warnings):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "incomplete_item",
                "message": "Der Itemtext ist nicht vollständig analysierbar.",
            },
        )
    is_staff = parsed.item.item_class == "Staves"
    if parsed.item.item_class != SLOT_CLASSES[request.target_slot] and not (
        is_staff and request.target_slot == "wand"
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "item_slot_mismatch",
                "message": "Die Item Class passt nicht zum gewählten Zielslot.",
            },
        )
    try:
        build = get_any_build(db, request.build_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_build", "message": "Der gewählte Build ist nicht verfügbar."},
        ) from exc
    from app.equipment.service import item_schema, profile_schema

    target_slots: list[Slot] = ["wand", "focus"] if is_staff else [request.target_slot]
    equipped_slots: dict[Slot, ParsedItem | None] = {}
    for target in target_slots:
        row = db.get(EquipmentSlot, (1, target))
        equipped_orm = db.get(Item, row.item_id) if row and row.item_id else None
        equipped_slots[target] = item_schema(equipped_orm) if equipped_orm else None
    equipped = equipped_slots[request.target_slot]
    if equipped is None and is_staff:
        equipped = equipped_slots["focus"]
    if equipped is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "equipped_item_required",
                "message": "Im gewählten Zielslot muss zuerst ein Item ausgerüstet werden.",
            },
        )
    profile = db.get(CharacterProfile, 1) if request.use_profile else None
    evaluation_input = EvaluationInput(
        candidate=parsed.item,
        equipped=equipped,
        equipped_slots=equipped_slots,
        target_slot=request.target_slot,
        target_slots=target_slots,
        observed_profile=profile_schema(profile) if profile else None,
        build=build,
    )
    try:
        provider = get_evaluation_provider()
        evaluation = await provider.evaluate(evaluation_input)
    except EvaluationProviderError as exc:
        return EvaluateItemResponse(
            parse=parsed,
            build=build,
            target_slot=request.target_slot,
            equipped=equipped,
            equipped_slots=equipped_slots,
            target_slots=target_slots,
            evaluation=None,
            provider=None,
            model=None,
            provider_status="unavailable",
            provider_error={"code": exc.code, "message": exc.public_message},
            disclaimer=(
                "API-Empfehlung nicht verfügbar. Es wurde keine lokale Empfehlung "
                "oder Ersatzbewertung erzeugt."
            ),
        )
    return EvaluateItemResponse(
        parse=parsed,
        build=build,
        target_slot=request.target_slot,
        equipped=equipped,
        equipped_slots=equipped_slots,
        target_slots=target_slots,
        evaluation=evaluation,
        provider=provider.name,
        model=provider.model,
        provider_status="success",
        provider_error=None,
        disclaimer=(
            "API-gestützter Candidate-vs-Equipped-Vergleich. Keine Marktwert- oder "
            "Crafting-Bewertung."
        ),
    )
