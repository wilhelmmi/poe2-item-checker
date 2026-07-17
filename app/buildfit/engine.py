from app.buildfit.config import BUILD_FIT_CONFIG, BuildFitConfig
from app.buildfit.schemas import Evidence, EvidenceGroups, LocalComparison, ScoredItem, SlotComparison
from app.comparison.engine import compare_hard_checks
from app.db.models import CharacterProfile
from app.schemas.items import ParsedItem
from app.schemas.management import Slot


def score_item(item: ParsedItem, slot: Slot, config: BuildFitConfig = BUILD_FIT_CONFIG) -> ScoredItem:
    points = config.base_score
    evidence = [Evidence(rule_id="base", points=config.base_score, message="Build-Fit-Basiswert.")]
    unknown = 0
    relevant = 0
    for index, modifier in enumerate(item.modifiers):
        key = modifier.normalized_key
        if key == "unknown":
            unknown += 1
            continue
        weight = config.modifier_weights.get(key)
        if weight is None:
            continue
        if key == "maximum_energy_shield" and item.energy_shield is not None:
            continue
        transformed_value = None
        cap = None
        factor = 1.0
        transformation = config.roll_transformations.get(key)
        if transformation is not None:
            if len(modifier.values) != 1:
                unknown += 1
                continue
            transformed_value = modifier.values[0]
            if transformed_value <= 0:
                unknown += 1
                continue
            cap = transformation.value_cap
            factor = max(transformation.minimum_factor, min(1.0, transformed_value / cap))
        awarded = round(weight * config.slot_multipliers.get(slot, {}).get(key, 1.0) * factor)
        points += awarded
        relevant += 1
        message = f"{key} ist für den Build relevant."
        if transformation:
            message += f" Rollwert wird bei {cap:g} gekappt."
        evidence.append(Evidence(rule_id=f"modifier.{key}.{index}", points=awarded, message=message,
                                 value=transformed_value, cap=cap))
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
    confidence = "low" if unknown >= 2 else "medium" if unknown else "high"
    return ScoredItem(
        score=score, evidence=evidence, unknown_modifier_count=unknown,
        completeness="partial" if unknown else "complete",
        warnings=["unknown_modifiers_present"] if unknown else [],
        confidence=confidence, known_relevant_modifier_count=relevant,
        rule_version=config.schema_version,
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
        groups = EvidenceGroups(
            candidate_winners=[entry for entry in candidate_score.evidence if entry.points > 0],
            candidate_losers=[entry for entry in candidate_score.evidence if entry.points < 0],
            equipped_winners=[entry for entry in equipped_score.evidence if entry.points > 0] if equipped_score else [],
            equipped_losers=[entry for entry in equipped_score.evidence if entry.points < 0] if equipped_score else [],
        )
        comparisons.append(SlotComparison(
            target_slot=target, candidate=candidate_score, equipped=equipped_score,
            delta=delta, delta_band=band, category=category, hard_checks=hard,
            warnings=[*candidate_score.warnings, *warnings],
            evidence_groups=groups,
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
