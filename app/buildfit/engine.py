from app.buildfit.config import BUILD_FIT_CONFIG
from app.buildfit.schemas import Evidence, LocalComparison, ScoredItem, SlotComparison
from app.comparison.engine import compare_hard_checks
from app.db.models import CharacterProfile
from app.schemas.items import ParsedItem
from app.schemas.management import Slot


def score_item(item: ParsedItem, slot: Slot) -> ScoredItem:
    config = BUILD_FIT_CONFIG
    points = config.base_score
    evidence = [Evidence(rule_id="base", points=config.base_score, message="Build-Fit-Basiswert.")]
    unknown = 0
    modifier_points: dict[str, int] = {}
    for modifier in item.modifiers:
        key = modifier.normalized_key
        if key == "unknown":
            unknown += 1
            continue
        weight = config.modifier_weights.get(key)
        if weight is None:
            continue
        if key == "maximum_energy_shield" and item.energy_shield is not None:
            continue
        awarded = round(weight * config.slot_multipliers.get(slot, {}).get(key, 1.0))
        points += awarded
        modifier_points[key] = modifier_points.get(key, 0) + awarded
    evidence.extend(
        Evidence(rule_id=f"modifier.{key}", points=awarded, message=f"{key} ist für den Build relevant.")
        for key, awarded in modifier_points.items()
    )
    if item.energy_shield is not None:
        awarded = min(config.defence_caps["energy_shield"], item.energy_shield // 20)
        points += awarded
        evidence.append(Evidence(rule_id="defence.energy_shield", points=awarded, message="Beobachtetes gesamtes Energy Shield."))
    score = max(0, min(100, points))
    if score != points:
        evidence.append(Evidence(
            rule_id="score.clamp", points=score - points,
            message=f"Rohwert {points} wurde auf den Bereich 0–100 begrenzt.",
        ))
    return ScoredItem(
        score=score, evidence=evidence, unknown_modifier_count=unknown,
        completeness="partial" if unknown else "complete",
        warnings=["unknown_modifiers_present"] if unknown else [],
    )


def classify_delta(delta: int) -> str:
    if delta >= 12:
        return "upgrade"
    if delta >= 5:
        return "conditional_upgrade"
    if delta >= -4:
        return "sidegrade"
    return "downgrade"


def delta_band(delta: int) -> str:
    if delta >= 12:
        return "major_upgrade"
    if delta >= 5:
        return "positive"
    if delta >= -4:
        return "sidegrade"
    if delta >= -11:
        return "negative"
    return "major_downgrade"


def compare_slots(
    candidate: ParsedItem, targets: list[Slot], equipment: dict[Slot, ParsedItem | None],
    known_slots: set[Slot], profile: CharacterProfile | None,
) -> LocalComparison:
    comparisons: list[SlotComparison] = []
    for target in targets:
        equipped = equipment.get(target)
        candidate_score = score_item(candidate, target)
        equipped_score = score_item(equipped, target) if equipped else None
        delta = candidate_score.score - equipped_score.score if equipped_score else None
        category = classify_delta(delta) if delta is not None else "unknown"
        band = delta_band(delta) if delta is not None else None
        hard = compare_hard_checks(
            candidate, equipped, profile, target, target in known_slots,
            remaining_equipment=equipment,
        )
        warnings = [check.code for check in hard.checks if check.status == "fail"]
        if any(
            (check.code.startswith("requirement_") or check.code.startswith("remaining_"))
            and check.status == "fail" for check in hard.checks
        ):
            category = "not_suitable"
        elif category in {"upgrade", "conditional_upgrade"} and any(
            check.status == "fail" for check in hard.checks
        ):
            category = "conditional_upgrade"
        elif category == "upgrade" and any(check.status == "unknown" for check in hard.checks):
            category = "conditional_upgrade"
        if category == "upgrade" and (
            candidate_score.completeness == "partial"
            or (equipped_score is not None and equipped_score.completeness == "partial")
        ):
            category = "conditional_upgrade"
        comparisons.append(SlotComparison(
            target_slot=target, candidate=candidate_score, equipped=equipped_score,
            delta=delta, delta_band=band, category=category, hard_checks=hard,
            warnings=[*candidate_score.warnings, *warnings],
        ))
    eligible = [
        value for value in comparisons
        if value.delta is not None and value.category not in {"not_suitable", "unknown"}
    ]
    recommended = None
    if eligible:
        best = max(value.delta for value in eligible)
        winners = [value.target_slot for value in eligible if value.delta == best]
        recommended = winners[0] if len(winners) == 1 else None
    return LocalComparison(comparisons=comparisons, recommended_target=recommended)
