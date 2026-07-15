from app.facts.config import FACTS_CONFIG
from app.facts.extraction import extract_item_facts
from app.facts.schemas import (
    CraftingAssessment,
    Evidence,
    FactsCheck,
    ItemFacts,
    ModifierFacts,
    Predicate,
    RuleBase,
    TradeAssessment,
)
from app.schemas.items import ParsedItem

DISCLAIMER = (
    "Lokaler regelbasierter Faktencheck: keine garantierte Marktpreisermittlung und keine "
    "Aussage über ein Upgrade für deinen Build."
)


def _compare(actual: object, predicate: Predicate) -> bool:
    if predicate.op == "eq":
        return actual == predicate.value
    if predicate.op == "contains":
        return isinstance(actual, str) and isinstance(predicate.value, str) and predicate.value in actual
    return isinstance(actual, (int, float)) and isinstance(predicate.value, (int, float)) and actual >= predicate.value


def _modifier_match(predicate: Predicate, modifier: ModifierFacts) -> str | None:
    if predicate.modifier_key and modifier.normalized_key != predicate.modifier_key:
        return None
    if predicate.field == "current_value":
        actual = modifier.current_values[0] if modifier.current_values else None
    else:
        actual = getattr(modifier, predicate.field)
    return f"modifier.{predicate.field}={actual}" if _compare(actual, predicate) else None


def _match_rule(rule: RuleBase, facts: ItemFacts) -> list[str] | None:
    matched: list[str] = []
    groups: dict[str, list[Predicate]] = {}
    for predicate in rule.predicates:
        if predicate.scope == "item":
            actual = getattr(facts, predicate.field)
            if not _compare(actual, predicate):
                return None
            matched.append(f"item.{predicate.field}={actual}")
        elif predicate.modifier_group:
            groups.setdefault(predicate.modifier_group, []).append(predicate)
        else:
            evidence = None
            for modifier in facts.modifiers:
                evidence = _modifier_match(predicate, modifier)
                if evidence is not None:
                    break
            if evidence is None:
                return None
            matched.append(evidence)
    for group_name, predicates in sorted(groups.items()):
        group_match = None
        for modifier in facts.modifiers:
            evidence = [_modifier_match(predicate, modifier) for predicate in predicates]
            if all(value is not None for value in evidence):
                group_match = [f"group.{group_name}", *evidence]
                break
        if group_match is None:
            return None
        matched.extend(group_match)
    return matched


def _assessment_data(rules: list[RuleBase], facts: ItemFacts) -> dict[str, object] | None:
    matches: list[tuple[RuleBase, list[str]]] = []
    for rule in rules:
        matched = _match_rule(rule, facts)
        if matched is not None:
            matches.append((rule, matched))
    if not matches:
        return None
    highest = max(rule.priority for rule, _ in matches)
    selected = sorted(
        ((rule, matched) for rule, matched in matches if rule.priority == highest),
        key=lambda pair: pair[0].id,
    )
    outcomes = {rule.outcome for rule, _ in selected}
    if len(outcomes) != 1:
        return None
    return dict(
        outcome=selected[0][0].outcome,
        confidence=selected[0][0].confidence,
        confidence_reasons=[
            f"Höchste passende Regelpriorität: {highest}.",
            f"Regelquelle: {selected[0][0].source}",
        ],
        evidence=[
            Evidence(rule_id=rule.id, message=rule.message, matched_facts=matched)
            for rule, matched in selected
        ],
    )


def _has_unknown_relevant_modifier(facts: ItemFacts) -> bool:
    return any(
        modifier.normalized_key == "unknown" and modifier.source != "granted_skill"
        for modifier in facts.modifiers
    )


def check_item_facts(item: ParsedItem) -> FactsCheck:
    config = FACTS_CONFIG
    facts = extract_item_facts(item)
    warnings: list[str] = []
    if facts.unknown_modifier_count:
        warnings.append("unknown_modifiers_present")
    if facts.slot_hint is None:
        warnings.append("slot_hint_unknown")
    fallback = dict(
        confidence="low",
        confidence_reasons=["Keine explizite lokale Regel deckt diese Faktkombination ab."],
        evidence=[],
    )
    warnings.extend(facts.warnings)
    if _has_unknown_relevant_modifier(facts):
        trade = {"outcome": "manual_review", **fallback}
        crafting = {"outcome": "needs_review", **fallback}
    else:
        trade = _assessment_data(config.trade_rules, facts) or {"outcome": "manual_review", **fallback}
        crafting = _assessment_data(config.crafting_rules, facts) or {"outcome": "needs_review", **fallback}
    return FactsCheck(
        facts=facts,
        trade=TradeAssessment.model_validate(trade),
        crafting=CraftingAssessment.model_validate(crafting),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
