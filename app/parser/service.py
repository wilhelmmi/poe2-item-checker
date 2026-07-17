import re

from app.parser.item_text import parse_item_text
from app.parser.line_breaks import suggest_line_breaks
from app.schemas.parsing import ParseItemResponse, ParseWarning
from app.schemas.items import ParsedItem

BLOCKING_WARNING_CODES = {
    "input_missing_line_breaks",
    "missing_item_identity",
    "no_modifiers_detected",
}
COLLAPSED_RARITY_RE = re.compile(r"\bRarity:\s*(Normal|Magic|Rare|Unique)\b")


def _unknown_locations(raw_text: str, unknown_lines: list[str]) -> tuple[list[int], list[str]]:
    source_lines = raw_text.splitlines()
    locations: list[int] = []
    originals: list[str] = []
    cursor = 0
    for unknown in unknown_lines:
        for index in range(cursor, len(source_lines)):
            if source_lines[index] == unknown or source_lines[index].strip() == unknown.strip():
                locations.append(index + 1)
                originals.append(source_lines[index])
                cursor = index + 1
                break
    return locations, originals


def parse_with_warnings(raw_text: str) -> ParseItemResponse:
    """Parse item text and derive deterministic, presentation-safe diagnostics."""
    warnings: list[ParseWarning] = []
    collapsed = len(raw_text.splitlines()) == 1 and (
        "--------" in raw_text or "Item Class:" in raw_text or "Rarity:" in raw_text
    )
    if collapsed:
        original_line = raw_text.splitlines()[0]
        item = ParsedItem(raw_text=raw_text, unknown_lines=[original_line])
        warnings.append(
            ParseWarning(
                code="input_missing_line_breaks",
                message="Der Itemtext enthält keine Zeilenumbrüche. Bitte füge sie manuell ein und analysiere erneut.",
                lines=[],
                raw_lines=[],
            )
        )
    else:
        item = parse_item_text(raw_text)
    if item.unknown_lines:
        lines, raw_lines = _unknown_locations(raw_text, item.unknown_lines)
        warnings.append(
            ParseWarning(
                code="unknown_lines_preserved",
                message="Unbekannte Zeilen wurden unverändert erhalten und sollten geprüft werden.",
                lines=lines,
                raw_lines=raw_lines,
            )
        )
    if not item.item_class or not item.rarity or not item.name:
        warnings.append(
            ParseWarning(
                code="missing_item_identity",
                message="Item Class, Rarity oder Item Name konnten nicht vollständig erkannt werden.",
                lines=[],
                raw_lines=[],
            )
        )
    if re.search(r"\{[^}]*Modifier", raw_text, re.IGNORECASE) and not item.modifiers:
        warnings.append(
            ParseWarning(
                code="no_modifiers_detected",
                message="Der Text enthält Modifier-Markierungen, aber es wurden keine Modifier erkannt.",
                lines=[],
                raw_lines=[],
            )
        )
    suggestion = suggest_line_breaks(raw_text) if collapsed else None
    status = "unchanged"
    if collapsed:
        rarity_match = COLLAPSED_RARITY_RE.search(raw_text)
        if rarity_match and rarity_match.group(1) == "Unique":
            status = "ambiguous"
        elif suggestion and rarity_match and rarity_match.group(1) in {"Normal", "Magic", "Rare"}:
            reparsed = parse_with_warnings(suggestion.suggested_text)
            has_identity = all((reparsed.item.item_class, reparsed.item.rarity, reparsed.item.name))
            if rarity_match.group(1) == "Rare":
                has_identity = has_identity and bool(reparsed.item.base_type)
            has_blocker = any(w.code in BLOCKING_WARNING_CODES for w in reparsed.warnings)
            status = (
                "safe"
                if has_identity and not has_blocker and not reparsed.item.unknown_lines
                else "ambiguous"
            )
        else:
            status = "ambiguous"
    return ParseItemResponse(
        item=item,
        warnings=warnings,
        line_break_suggestion=suggestion,
        auto_format_status=status,
    )


def parse_with_safe_auto_format(raw_text: str) -> ParseItemResponse:
    """Apply only a parser-certified insert-only format; never guess ambiguous input."""
    parsed = parse_with_warnings(raw_text)
    if parsed.auto_format_status == "safe" and parsed.line_break_suggestion:
        return parse_with_warnings(parsed.line_break_suggestion.suggested_text)
    return parsed
