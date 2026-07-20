from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterProfile, EquipmentSlot, Item, Modifier
from app.builds.registry import DEFAULT_BUILD_ID
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
    StructuredEquipmentImport,
    StructuredEquipmentItem,
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


def item_slots(item_class: str, ring_slot: Slot = "ring_1") -> tuple[Slot, ...]:
    if item_class == "Staves":
        return ("wand", "focus")
    if item_class == "Rings":
        return (ring_slot,)
    return tuple(slot for slot, expected in SLOT_CLASSES.items() if expected == item_class)[:1]


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


def equipment_response(db: Session, build_id: str = DEFAULT_BUILD_ID) -> EquipmentResponse:
    rows = db.execute(select(EquipmentSlot).where(
        EquipmentSlot.character_id == 1, EquipmentSlot.build_id == build_id
    )).scalars()
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


def replace_equipment(db: Session, slot: Slot, raw_text: str, build_id: str = DEFAULT_BUILD_ID) -> EquipmentItem:
    parsed = parse_equipment(raw_text, auto_format=True)
    if parsed.item_class == "Staves" and slot == "wand":
        pass
    elif parsed.item_class != SLOT_CLASSES[slot]:
        raise ValueError("item_slot_mismatch")
    get_or_create_profile(db)
    item = store_item(db, parsed)
    row = db.get(EquipmentSlot, (1, build_id, slot))
    if row is None:
        row = EquipmentSlot(character_id=1, build_id=build_id, slot=slot, item_id=item.id)
        db.add(row)
    else:
        row.item_id = item.id
    # A staff occupies both hand slots, represented canonically in wand. Equipping a
    # focus removes an existing staff so no illegal staff+focus state can be committed.
    conflicting_slot = "focus" if parsed.item_class == "Staves" else "wand" if slot == "focus" else None
    if conflicting_slot:
        conflict = db.get(EquipmentSlot, (1, build_id, conflicting_slot))
        if parsed.item_class == "Staves" or (
            conflict and conflict.item_id and item_schema(db.get(Item, conflict.item_id)).item_class == "Staves"
        ):
            if conflict is None:
                db.add(EquipmentSlot(character_id=1, build_id=build_id, slot=conflicting_slot, item_id=None))
            else:
                conflict.item_id = None
    db.commit()
    return EquipmentItem(id=item.id, item=item_schema(item))


def equip_loadout(db: Session, raw_text: str, ring_slot: Slot = "ring_1", build_id: str = DEFAULT_BUILD_ID) -> EquipmentResponse:
    parsed = parse_equipment(raw_text, auto_format=True)
    targets = item_slots(parsed.item_class or "", ring_slot)
    if not targets:
        raise ValueError("unsupported_item_class")
    replace_equipment(db, targets[0], parsed.raw_text, build_id)
    return equipment_response(db, build_id)


def structured_item_text(item: StructuredEquipmentItem) -> str:
    lines = [
        f"Item Class: {item.item_class}",
        f"Rarity: {item.rarity}",
        item.name,
        item.base,
        "--------",
    ]
    if item.energy_shield is not None:
        lines.extend((f"Energy Shield: {item.energy_shield}", "--------"))
    if item.item_level is not None:
        lines.extend((f"Item Level: {item.item_level}", "--------"))
    for modifier in item.mods:
        lines.extend(("{ Prefix Modifier }", modifier))
    return "\n".join(lines)


def structured_equipment_text(data: StructuredEquipmentImport) -> dict[Slot, str]:
    source = data.model_dump()
    source["ring_1"] = source.pop("ring1")
    source["ring_2"] = source.pop("ring2")
    source.pop("charms")
    return {
        slot: structured_item_text(StructuredEquipmentItem.model_validate(source[slot]))
        for slot in SLOTS
    }


def import_equipment(db: Session, data: EquipmentImportData, build_id: str = DEFAULT_BUILD_ID) -> EquipmentResponse:
    raw_text = (
        structured_equipment_text(data)
        if isinstance(data, StructuredEquipmentImport)
        else data.equipment_raw_text
    )
    parsed = {
        slot: parse_equipment(raw)
        for slot, raw in raw_text.items()
        if raw is not None
    }
    if any(
        item.item_class != SLOT_CLASSES[slot]
        and not (slot == "wand" and item.item_class == "Staves")
        for slot, item in parsed.items()
    ):
        raise ValueError("item_slot_mismatch")
    imported_staff = parsed.get("wand") and parsed["wand"].item_class == "Staves"
    imported_focus = parsed.get("focus") is not None
    if imported_staff and imported_focus:
        raise ValueError("two_handed_slot_conflict")
    profile = get_or_create_profile(db)
    if isinstance(data, StructuredEquipmentImport):
        pass
    elif data.schema_version == 1:
        profile.name = data.profile.name
        profile.build_stage = data.profile.build_stage
        for key, value in data.profile.character_sheet.model_dump().items():
            setattr(profile, key, value)
    else:
        for key, value in data.profile.model_dump().items():
            setattr(profile, key, value)
    for slot, item_data in parsed.items():
        item = store_item(db, item_data)
        row = db.get(EquipmentSlot, (1, build_id, slot))
        if row is None:
            db.add(EquipmentSlot(character_id=1, build_id=build_id, slot=slot, item_id=item.id))
        else:
            row.item_id = item.id
    # Partial v1 imports obey the same deterministic hand-slot semantics as
    # individual equips: a newly imported staff clears focus; a newly imported
    # focus clears an already equipped staff. A payload containing both conflicts
    # and is rejected above rather than depending on mapping order.
    if imported_staff:
        focus_row = db.get(EquipmentSlot, (1, build_id, "focus"))
        if focus_row is None:
            db.add(EquipmentSlot(character_id=1, build_id=build_id, slot="focus", item_id=None))
        else:
            focus_row.item_id = None
    elif imported_focus:
        wand_row = db.get(EquipmentSlot, (1, build_id, "wand"))
        wand_item = db.get(Item, wand_row.item_id) if wand_row and wand_row.item_id else None
        if wand_item is not None and item_schema(wand_item).item_class == "Staves":
            wand_row.item_id = None
    if not isinstance(data, StructuredEquipmentImport) and data.schema_version == 2:
        for slot, raw in raw_text.items():
            if raw is None:
                row = db.get(EquipmentSlot, (1, build_id, slot))
                if row is None:
                    db.add(EquipmentSlot(character_id=1, build_id=build_id, slot=slot, item_id=None))
                else:
                    row.item_id = None
    db.commit()
    return equipment_response(db, build_id)


def export_equipment(db: Session, build_id: str = DEFAULT_BUILD_ID) -> EquipmentExport:
    profile = get_or_create_profile(db)
    current = equipment_response(db, build_id)
    raw = {slot: value.item.raw_text if value else None for slot, value in current.slots.items()}
    return EquipmentExport(
        profile=profile_schema(profile),
        equipment_raw_text=raw,
    )
