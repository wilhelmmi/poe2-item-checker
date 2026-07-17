from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterProfile, EquipmentSlot, Item, Modifier
from app.parser.service import (
    BLOCKING_WARNING_CODES,
    parse_with_safe_auto_format,
    parse_with_warnings,
)
from app.schemas.items import ModifierData, ParsedItem
from app.schemas.management import (
    SLOTS,
    EquipmentExport,
    EquipmentImportData,
    EquipmentItem,
    EquipmentResponse,
    ProfileData,
    Slot,
)

BLOCKING = {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"}
SLOT_CLASSES = {
    "wand": "Wands",
    "focus": "Foci",
    "helmet": "Helmets",
    "body_armour": "Body Armours",
    "gloves": "Gloves",
    "boots": "Boots",
    "belt": "Belts",
    "ring_1": "Rings",
    "ring_2": "Rings",
    "amulet": "Amulets",
}


def get_or_create_profile(db: Session) -> CharacterProfile:
    profile = db.get(CharacterProfile, 1)
    if profile is None:
        profile = CharacterProfile(
            id=1, name="Chaos DoT Lich", build_stage="early_endgame", notes=""
        )
        db.add(profile)
        db.flush()
    return profile


def profile_schema(profile: CharacterProfile) -> ProfileData:
    return ProfileData.model_validate(
        {field: getattr(profile, field) for field in ProfileData.model_fields}
    )


def put_profile(db: Session, data: ProfileData) -> ProfileData:
    profile = get_or_create_profile(db)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    return profile_schema(profile)


def parse_equipment(raw_text: str, *, auto_format: bool = False) -> ParsedItem:
    preflight = parse_with_warnings(raw_text)
    if preflight.auto_format_status == "ambiguous":
        raise ValueError("ambiguous_item_format")
    parsed = parse_with_safe_auto_format(raw_text) if auto_format else preflight
    if any(warning.code in BLOCKING_WARNING_CODES for warning in parsed.warnings):
        raise ValueError("incomplete_item")
    return parsed.item


def store_item(db: Session, parsed: ParsedItem) -> Item:
    values = parsed.model_dump(exclude={"modifiers"})
    item = Item(**values)
    item.modifiers = [Modifier(**modifier.model_dump()) for modifier in parsed.modifiers]
    db.add(item)
    db.flush()
    return item


def item_schema(item: Item) -> ParsedItem:
    values = {
        field: getattr(item, field) for field in ParsedItem.model_fields if field != "modifiers"
    }
    values["modifiers"] = [
        ModifierData.model_validate(
            {field: getattr(modifier, field) for field in ModifierData.model_fields}
        )
        for modifier in item.modifiers
    ]
    return ParsedItem.model_validate(values)


def equipment_response(db: Session) -> EquipmentResponse:
    rows = db.execute(select(EquipmentSlot).where(EquipmentSlot.character_id == 1)).scalars()
    mapping = {row.slot: row for row in rows}
    slots: dict[Slot, EquipmentItem | None] = {}
    for slot in SLOTS:
        row = mapping.get(slot)
        if row is None:
            slots[slot] = None
        else:
            item = db.get(Item, row.item_id) if row.item_id else None
            slots[slot] = EquipmentItem(id=item.id, item=item_schema(item)) if item else None
    return EquipmentResponse(slots=slots)


def replace_equipment(db: Session, slot: Slot, raw_text: str) -> EquipmentItem:
    parsed = parse_equipment(raw_text, auto_format=True)
    if parsed.item_class != SLOT_CLASSES[slot]:
        raise ValueError("item_slot_mismatch")
    get_or_create_profile(db)
    item = store_item(db, parsed)
    row = db.get(EquipmentSlot, (1, slot))
    if row is None:
        row = EquipmentSlot(character_id=1, slot=slot, item_id=item.id)
        db.add(row)
    else:
        row.item_id = item.id
    db.commit()
    return EquipmentItem(id=item.id, item=item_schema(item))


def import_equipment(db: Session, data: EquipmentImportData) -> EquipmentResponse:
    parsed = {
        slot: parse_equipment(raw)
        for slot, raw in data.equipment_raw_text.items()
        if raw is not None
    }
    if any(item.item_class != SLOT_CLASSES[slot] for slot, item in parsed.items()):
        raise ValueError("item_slot_mismatch")
    profile = get_or_create_profile(db)
    if data.schema_version == 1:
        profile.name = data.profile.name
        profile.build_stage = data.profile.build_stage
        for key, value in data.profile.character_sheet.model_dump().items():
            setattr(profile, key, value)
    else:
        for key, value in data.profile.model_dump().items():
            setattr(profile, key, value)
    for slot, item_data in parsed.items():
        item = store_item(db, item_data)
        row = db.get(EquipmentSlot, (1, slot))
        if row is None:
            db.add(EquipmentSlot(character_id=1, slot=slot, item_id=item.id))
        else:
            row.item_id = item.id
    if data.schema_version == 2:
        for slot, raw in data.equipment_raw_text.items():
            if raw is None:
                row = db.get(EquipmentSlot, (1, slot))
                if row is None:
                    db.add(EquipmentSlot(character_id=1, slot=slot, item_id=None))
                else:
                    row.item_id = None
    db.commit()
    return equipment_response(db)


def export_equipment(db: Session) -> EquipmentExport:
    profile = get_or_create_profile(db)
    current = equipment_response(db)
    raw = {slot: value.item.raw_text if value else None for slot, value in current.slots.items()}
    return EquipmentExport(
        profile=profile_schema(profile),
        equipment_raw_text=raw,
    )
