from app.comparison.schemas import HardCheck, HardChecks
from app.db.models import CharacterProfile
from app.schemas.items import ParsedItem
from app.schemas.management import Slot


def _value(item: ParsedItem | None, key: str) -> float:
    if item is None:
        return 0
    total = 0.0
    for modifier in item.modifiers:
        if modifier.normalized_key == key and modifier.values:
            total += modifier.values[0]
        if key in {"strength", "dexterity", "intelligence"} and modifier.normalized_key == "all_attributes" and modifier.values:
            total += modifier.values[0]
    return total


def _threshold(code: str, before: float | None, after: float | None, required: float | None) -> HardCheck:
    if after is None or required is None:
        status = "unknown"
    else:
        status = "pass" if after >= required else "fail"
    return HardCheck(code=code, status=status, message={
        "pass": "Die bekannte Anforderung bleibt erfüllt.",
        "fail": "Die bekannte Anforderung wäre nach dem Tausch nicht erfüllt.",
        "unknown": "Für diese harte Prüfung fehlen Werte.",
    }[status], before=before, after=after, required=required)


def compare_hard_checks(
    candidate: ParsedItem, equipped: ParsedItem | None,
    profile: CharacterProfile | None, target_slot: str | None,
    replacement_known: bool = False,
    remaining_equipment: dict[Slot, ParsedItem | None] | None = None,
) -> HardChecks:
    checks: list[HardCheck] = []
    for key, requirement in (
        ("level", candidate.required_level), ("strength", candidate.required_strength),
        ("dexterity", candidate.required_dexterity), ("intelligence", candidate.required_intelligence),
    ):
        base = getattr(profile, "character_level" if key == "level" else key, None) if profile else None
        after = base
        if base is not None and key != "level":
            # Without a target slot the removed item's contribution is unknowable.
            after = None if not replacement_known else base - _value(equipped, key)
        checks.append(_threshold(f"requirement_{key}", base, after, requirement))
    if profile and replacement_known and remaining_equipment is not None:
        for slot, item in remaining_equipment.items():
            if slot == target_slot or item is None:
                continue
            for key, required in (
                ("level", item.required_level), ("strength", item.required_strength),
                ("dexterity", item.required_dexterity), ("intelligence", item.required_intelligence),
            ):
                base = getattr(profile, "character_level" if key == "level" else key)
                after = base
                if base is not None and key != "level":
                    after = base - _value(equipped, key) + _value(candidate, key)
                checks.append(_threshold(f"remaining_{slot}_{key}", base, after, required))
    cap = profile.resistance_cap if profile else None
    for key in ("fire", "cold", "lightning", "chaos"):
        before = getattr(profile, f"{key}_resistance", None) if profile else None
        after = None if before is None or not replacement_known else before - _value(equipped, f"{key}_resistance") + _value(candidate, f"{key}_resistance")
        if key in {"fire", "cold", "lightning"}:
            if before is None or after is None or cap is None:
                status = "unknown"
            else:
                status = "fail" if before >= cap and after < cap else "pass"
            checks.append(HardCheck(
                code=f"resistance_{key}", status=status,
                message=("Der Tausch drückt eine zuvor gecappte Resistance unter das Cap."
                         if status == "fail" else "Kein neuer Verlust des Resistance-Caps."
                         if status == "pass" else "Für diese harte Prüfung fehlen Werte."),
                before=before, after=after, required=cap,
            ))
        else:
            checks.append(_threshold(f"resistance_{key}", before, after, cap))
    spirit_before = profile.spirit if profile else None
    spirit_after = None if spirit_before is None or not replacement_known else spirit_before - _value(equipped, "spirit") + _value(candidate, "spirit")
    required_values = [value for value in (
        profile.spirit_required if profile else None, profile.spirit_reserved if profile else None,
    ) if value is not None]
    checks.append(_threshold("spirit", spirit_before, spirit_after, max(required_values) if required_values else None))
    if target_slot == "boots":
        before = _value(equipped, "movement_speed") if replacement_known else None
        after = _value(candidate, "movement_speed")
        status = "unknown" if before is None else ("fail" if before - after >= 10 else "pass")
        checks.append(HardCheck(
            code="boots_movement_speed_loss", status=status,
            message=("Movement Speed sinkt beim Tausch um mindestens 10 Prozentpunkte." if status == "fail" else
                     "Kein starker Movement-Speed-Verlust." if status == "pass" else
                     "Aktuelle Boots fehlen für den Vergleich."),
            before=before, after=after, required=before,
        ))
    return HardChecks(target_slot=target_slot, checks=checks)
