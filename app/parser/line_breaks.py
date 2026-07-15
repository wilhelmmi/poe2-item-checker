import re

from app.parser.modifier_headers import parse_modifier_header
from app.schemas.parsing import LineBreakInsertion, LineBreakSuggestion

SEPARATOR_RE = re.compile(r"(?<!\S)--------(?!\S)")
EXPORT_HEADER_RE = re.compile(
    r"\A[ \t]*Item Class:[ \t]+(?P<item_class>(?:(?!Rarity:)[^\r\n])*?\S)"
    r"[ \t]+(?P<rarity_label>Rarity:)"
    r"[ \t]+(?P<rarity>Normal|Magic|Rare|Unique)\b"
)
BRACED_RE = re.compile(r"\{[^{}]*\}")

MESSAGES = {
    "before_separator": "Zeilenumbruch vor einem exakten Trennmarker eingefügt.",
    "after_separator": "Zeilenumbruch nach einem exakten Trennmarker eingefügt.",
    "before_rarity": "Zeilenumbruch zwischen Item Class und Rarity eingefügt.",
    "after_rarity": "Zeilenumbruch nach der kanonischen Rarity eingefügt.",
    "before_modifier_header": "Zeilenumbruch vor einem vollständigen Modifierheader eingefügt.",
    "after_modifier_header": "Zeilenumbruch nach einem vollständigen Modifierheader eingefügt.",
}


def suggest_line_breaks(raw_text: str) -> LineBreakSuggestion | None:
    """Return an insert-only, conservative line-break proposal for collapsed input."""
    if "\n" in raw_text or "\r" in raw_text:
        return None
    export_header = EXPORT_HEADER_RE.match(raw_text)
    if export_header is None:
        return None
    candidates: dict[int, str] = {}

    def add(offset: int, code: str) -> None:
        if 0 < offset < len(raw_text):
            candidates.setdefault(offset, code)

    for match in SEPARATOR_RE.finditer(raw_text):
        add(match.start(), "before_separator")
        add(match.end(), "after_separator")
    add(export_header.start("rarity_label"), "before_rarity")
    add(export_header.end("rarity"), "after_rarity")
    for match in BRACED_RE.finditer(raw_text):
        if parse_modifier_header(match.group(0)) is not None:
            add(match.start(), "before_modifier_header")
            add(match.end(), "after_modifier_header")
    if not candidates:
        return None
    insertions = [
        LineBreakInsertion(offset=offset, code=code, message=MESSAGES[code])
        for offset, code in sorted(candidates.items())
    ]
    pieces: list[str] = []
    cursor = 0
    for insertion in insertions:
        pieces.extend((raw_text[cursor:insertion.offset], "\n"))
        cursor = insertion.offset
    pieces.append(raw_text[cursor:])
    return LineBreakSuggestion(suggested_text="".join(pieces), insertions=insertions)
