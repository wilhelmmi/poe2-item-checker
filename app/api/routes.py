from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import (
    BuildImpacts,
    EvaluateItemRequest,
    EvaluateItemResponse,
    EvaluationInput,
    EvaluationResult,
)
from app.evaluation.service import get_evaluation_provider
from app.builds.registry import BuildContext
from app.builds.provider_service import get_build_provider
from app.builds.schemas import (ActiveBuild, BuildCitation, BuildPreviewRequest,
                                BuildPreviewResponse, DeletedBuild)
from app.builds.service import (canonicalize_source_url, confirm_preview, create_preview,
                                delete_custom_build, get_active, get_any_build, list_all_builds,
                                row_context, set_active)
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
    comparison_slots,
    charm_slot_context,
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


def _citation_key(url: str) -> tuple[str, str, int | None, str, str]:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    port = parsed.port
    if (scheme, port) in {("http", 80), ("https", 443)}:
        port = None
    return scheme, (parsed.hostname or "").lower(), port, parsed.path or "/", parsed.query


def _include_source_citation(source_url: str,
                             citations: list[BuildCitation]) -> list[BuildCitation]:
    source = BuildCitation(url=source_url, title="Original-Build")
    source_key = _citation_key(str(source.url))
    safe_citations: list[BuildCitation] = []
    for citation in citations:
        citation_url = str(citation.url)
        validation_url = urlsplit(citation_url)._replace(fragment="").geturl()
        try:
            canonicalize_source_url(validation_url)
        except ValueError:
            continue
        safe_citations.append(citation)
    if any(_citation_key(str(citation.url)) == source_key for citation in safe_citations):
        return safe_citations
    return [source, *safe_citations]


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
    if data.build_id is None:
        raise HTTPException(422, detail={"code": "unknown_build", "message": "Der Build ist nicht verfügbar."})
    try:
        return ActiveBuild(build_id=set_active(db, data.build_id))
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "unknown_build", "message": "Der Build ist nicht verfügbar."}) from exc


@router.delete("/builds/{build_id}", response_model=DeletedBuild)
async def delete_build(build_id: str, db: Session = Depends(database)) -> DeletedBuild:
    try:
        active_build_id = delete_custom_build(db, build_id)
    except ValueError as exc:
        raise HTTPException(404, detail={"code": "unknown_build", "message": "Der Build ist nicht verfügbar."}) from exc
    return DeletedBuild(deleted_build_id=build_id, active_build_id=active_build_id)


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
    citations = _include_source_citation(source_url, citations)
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


def require_build(db: Session, build_id: str) -> None:
    try:
        get_any_build(db, build_id)
    except ValueError as exc:
        raise HTTPException(404, detail={"code": "unknown_build", "message": "Der Build ist nicht verfügbar."}) from exc


@router.get("/builds/{build_id}/equipment", response_model=EquipmentResponse)
async def get_equipment(build_id: str, db: Session = Depends(database)) -> EquipmentResponse:
    require_build(db, build_id)
    return equipment_response(db, build_id)


@router.put("/builds/{build_id}/equipment/{slot}", response_model=EquipmentItem)
async def put_equipment(
    build_id: str, slot: Slot, data: EquipmentPut, db: Session = Depends(database)
) -> EquipmentItem:
    try:
        require_build(db, build_id)
        if slot.startswith("charm_"):
            _, available, _ = charm_slot_context(db, build_id)
            if slot not in available:
                raise ValueError("charm_slot_locked")
        return replace_equipment(db, slot, data.raw_text, build_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/builds/{build_id}/equipment/equip", response_model=EquipmentResponse)
async def equip_item(build_id: str, data: EquipmentEquip, db: Session = Depends(database)) -> EquipmentResponse:
    try:
        require_build(db, build_id)
        return equip_loadout(db, data.raw_text, data.target_slot or data.ring_slot, build_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/builds/{build_id}/equipment/import", response_model=EquipmentResponse)
async def import_equipment_seed(
    build_id: str, data: EquipmentImportData, db: Session = Depends(database)
) -> EquipmentResponse:
    try:
        require_build(db, build_id)
        return import_equipment(db, data, build_id)
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


@router.get("/builds/{build_id}/equipment/export", response_model=EquipmentExport)
async def get_equipment_export(build_id: str, db: Session = Depends(database)) -> EquipmentExport:
    require_build(db, build_id)
    return export_equipment(db, build_id)


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

    candidate_comparison_slots = list(comparison_slots(parsed.item.item_class or ""))
    available_target_slots = list(candidate_comparison_slots)
    if parsed.item.item_class == "Charms":
        _, available, charm_comparisons = charm_slot_context(db, request.build_id)
        available_target_slots = list(available)
        candidate_comparison_slots = list(charm_comparisons)
        if request.target_slot not in available_target_slots:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "charm_slot_locked",
                    "message": "Der gewählte Charm-Slot ist durch den aktuellen Gürtel gesperrt.",
                },
            )
    if not candidate_comparison_slots:
        raise HTTPException(422, detail={"code": "unsupported_item_class"})
    is_alternative = parsed.item.item_class in {"Rings", "Charms"}
    selected_target = request.target_slot
    target_slots: list[Slot] = ["wand", "focus"] if is_staff else [selected_target]
    equipped_slots: dict[Slot, ParsedItem | None] = {}
    for target in candidate_comparison_slots:
        row = db.get(EquipmentSlot, (1, request.build_id, target))
        equipped_orm = db.get(Item, row.item_id) if row and row.item_id else None
        equipped_slots[target] = item_schema(equipped_orm) if equipped_orm else None
    empty_slots = [slot for slot in available_target_slots if equipped_slots[slot] is None]
    if is_alternative and empty_slots:
        selected_target = empty_slots[0]
        target_slots = [selected_target]
    equipped = equipped_slots.get(selected_target)
    if equipped is None and not is_alternative:
        equipped = next((item for item in equipped_slots.values() if item is not None), None)
    if equipped is None and not is_alternative:
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
        target_slot=selected_target,
        target_slots=target_slots,
        comparison_slots=candidate_comparison_slots,
        available_target_slots=available_target_slots,
        observed_profile=profile_schema(profile) if profile else None,
        build=build,
    )
    provider = None
    if is_alternative and equipped is None:
        slot_label = selected_target.replace("_", " ").title()
        evaluation = EvaluationResult(
            recommendation="better",
            confidence="high",
            reasons=[f"{slot_label} ist frei; beim Ausrüsten gehen keine Itemwerte verloren."],
            verdict="upgrade",
            current_item_name=f"Leerer {slot_label}",
            new_item_name=parsed.item.name or parsed.item.base_type or "Neues Item",
            gains=["Ein bisher leerer Ausrüstungsplatz wird belegt."],
            losses=[],
            impacts=BuildImpacts(
                damage="similar", defensive="similar", resistances="similar", utility="better"
            ),
            clear_recommendation="Ausrüsten, da der Zielslot frei ist und keine Werte verloren gehen.",
            recommended_target_slot=selected_target,
        )
    else:
        try:
            provider = get_evaluation_provider()
            evaluation = await provider.evaluate(evaluation_input)
        except EvaluationProviderError as exc:
            return EvaluateItemResponse(
                parse=parsed,
                build=build,
                target_slot=selected_target,
                equipped=equipped,
                equipped_slots=equipped_slots,
                target_slots=target_slots,
                comparison_slots=candidate_comparison_slots,
                available_target_slots=available_target_slots,
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
    if is_alternative:
        if empty_slots and evaluation.recommended_target_slot == selected_target:
            pass
        elif not empty_slots and evaluation.recommended_target_slot in available_target_slots:
            selected_target = evaluation.recommended_target_slot
        else:
            raise HTTPException(
                status_code=502,
                detail={"code": "invalid_provider_response", "message": (
                    "Die AI-Bewertung hat keinen gültigen Ersatzslot empfohlen."
                )},
            )
        target_slots = [selected_target]
    return EvaluateItemResponse(
        parse=parsed,
        build=build,
        target_slot=selected_target,
        equipped=equipped,
        equipped_slots=equipped_slots,
        target_slots=target_slots,
        comparison_slots=candidate_comparison_slots,
        available_target_slots=available_target_slots,
        evaluation=evaluation,
        provider=provider.name if provider else "system",
        model=provider.model if provider else "empty-slot-rule",
        provider_status="success",
        provider_error=None,
        disclaimer=(
            "API-gestützter Candidate-vs-Equipped-Vergleich. Keine Marktwert- oder "
            "Crafting-Bewertung."
        ),
    )
