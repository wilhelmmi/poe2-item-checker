import re

from app.parser.modifier_headers import ModifierHeader, parse_modifier_header
from app.parser.normalizations import normalize_modifier
from app.parser.localization import canonical_item_class, canonical_rarity
from app.schemas.items import ModifierData, ParsedItem

NUMBER_RE = re.compile(
    r"(?<![A-Za-z])([+-]?\d+(?:[.,]\d+)?)(?:\(([-+]?\d+(?:[.,]\d+)?)-([-+]?\d+(?:[.,]\d+)?)\))?"
)


def _number(value: str) -> int | float:
    parsed = float(value.replace(",", "."))
    return int(parsed) if parsed.is_integer() else parsed


def _modifier(line: str, header: ModifierHeader | None = None) -> ModifierData:
    source = header.source if header else "explicit"
    annotation = re.search(
        r"\((rune|crafted|desecrated|implicit|hergestellt|entweiht|implizit)\)\s*$",
        line, re.I,
    )
    if annotation:
        source = {
            "hergestellt": "crafted", "entweiht": "desecrated", "implizit": "implicit"
        }.get(annotation.group(1).lower(), annotation.group(1).lower())
    matches = list(NUMBER_RE.finditer(line))
    values = [_number(match.group(1)) for match in matches]
    ranges = [
        [_number(match.group(2)), _number(match.group(3))]
        for match in matches
        if match.group(2)
    ]
    normalized = normalize_modifier(line)
    return ModifierData(
        source=source,
        affix_type=header.affix_type if header else None,
        name=header.name if header else None,
        tier=header.tier if header else None,
        tags=list(header.tags) if header else [],
        raw_text=line,
        normalized_key=normalized,
        values=values,
        roll_ranges=ranges,
        crafted=source == "crafted",
        desecrated=source == "desecrated",
        rune=source == "rune",
        implicit=source == "implicit",
        unique=source == "unique",
    )


def _blocks(raw_text: str) -> list[list[str]]:
    blocks: list[list[str]] = [[]]
    for line in raw_text.splitlines():
        if line.strip() == "--------":
            blocks.append([])
        elif line.strip():
            blocks[-1].append(line)
    return blocks


def _parse_identity(block: list[str], data: dict[str, object]) -> None:
    remaining: list[str] = []
    for line in block:
        stripped = line.strip()
        identity = re.match(r"(?:Item Class|Gegenstandsklasse):\s*(.+)", stripped, re.I)
        rarity_line = re.match(r"(?:Rarity|Seltenheit):\s*(.+)", stripped, re.I)
        if identity:
            data["item_class"] = canonical_item_class(identity.group(1))
        elif rarity_line:
            data["rarity"] = canonical_rarity(rarity_line.group(1))
        else:
            remaining.append(stripped)
    rarity = data.get("rarity")
    if rarity in {"Rare", "Unique"} and len(remaining) >= 2:
        data["name"], data["base_type"] = remaining[:2]
        data["unknown_lines"].extend(remaining[2:])  # type: ignore[union-attr]
    elif remaining:
        # Normal and Magic exports have a single identity line. A magic base cannot be
        # inferred reliably from the decorated name, so base_type intentionally stays null.
        data["name"] = remaining[0]
        if rarity == "Normal":
            data["base_type"] = remaining[0]
        extra_identity_lines = remaining[1:]
        if rarity == "Normal":
            extra_identity_lines = [line for line in extra_identity_lines if line != remaining[0]]
        data["unknown_lines"].extend(extra_identity_lines)  # type: ignore[union-attr]


def _parse_structured(line: str, data: dict[str, object], requirements: bool) -> bool:
    stripped = line.strip()
    compact = re.match(r"(?:Requires|Erfordert):\s*(.+)", stripped, re.I)
    if compact:
        requirements_text = compact.group(1)
        pairs = re.findall(r"(Level|Stufe|Str|Dex|Ges|Int)\s+(\d+)", requirements_text, re.I)
        pairs.extend((label, value) for value, label in re.findall(r"(\d+)\s+(Level|Stufe|Str|Dex|Ges|Int)", requirements_text, re.I))
        for label, value in pairs:
            key = {"level": "required_level", "stufe": "required_level", "str": "required_strength",
                   "dex": "required_dexterity", "ges": "required_dexterity",
                   "int": "required_intelligence"}[label.lower()]
            data[key] = int(value)
        return True
    requirement = re.match(r"(Level|Stufe|Str|Dex|Ges|Int):\s*(\d+)", stripped, re.I)
    if requirements and requirement:
        key = {"level": "required_level", "stufe": "required_level", "str": "required_strength",
               "dex": "required_dexterity", "ges": "required_dexterity",
               "int": "required_intelligence"}[requirement.group(1).lower()]
        data[key] = int(requirement.group(2))
        return True
    prop = re.match(
        r"(Item Level|Gegenstandsstufe|Quality|Qualität|Armour|Rüstung|Evasion|Ausweichwert|"
        r"Energy Shield|Energieschild|Spirit|Willenskraft):\s*\+?(\d+)(.*)$", stripped, re.I,
    )
    if prop:
        key = {
            "gegenstandsstufe": "item_level", "qualität": "quality", "rüstung": "armour",
            "ausweichwert": "evasion", "energieschild": "energy_shield",
            "willenskraft": "spirit",
        }.get(prop.group(1).lower(), prop.group(1).lower().replace(" ", "_"))
        data[key] = int(prop.group(2))
        if key in {"armour", "evasion", "energy_shield"}:
            data[f"{key}_augmented"] = bool(re.search(r"\((?:augmented|erhöht|verstärkt)\)", prop.group(3), re.I))
        return True
    sockets = re.match(r"(?:Sockets|Fassungen):\s*(.+)", stripped, re.I)
    if sockets:
        data["sockets"] = sockets.group(1).split()
        return True
    grants = re.match(r"(?:Grants Skill|Gewährt Fertigkeit):\s*(.+)", stripped, re.I)
    if grants:
        skill = grants.group(1)
        data["granted_skill"] = skill
        data["modifiers"].append(  # type: ignore[union-attr]
            _modifier(skill, ModifierHeader(source="granted_skill"))
        )
        return True
    if stripped in {"Corrupted", "Verderbt"}:
        data["corrupted"] = True
        return True
    if stripped in {"Unidentified", "Nicht identifiziert"}:
        data["identified"] = False
        return True
    return stripped in {"Requirements:", "Anforderungen:"}


def parse_item_text(raw_text: str) -> ParsedItem:
    """Parse English item text deterministically while retaining all original information.

    Each content line of a multi-line affix becomes its own modifier and receives an
    identical copy of the preceding header metadata. This avoids inventing line-joining
    semantics while keeping tier, affix and tag information attached to every line.
    """
    data: dict[str, object] = {"raw_text": raw_text, "unknown_lines": [], "modifiers": []}
    blocks = _blocks(raw_text)
    if blocks:
        _parse_identity(blocks[0], data)

    for block_index, block in enumerate(blocks[1:], start=1):
        requirements = bool(block and block[0].strip() in {"Requirements:", "Anforderungen:"})
        active_header: ModifierHeader | None = None
        block_has_header = any(parse_modifier_header(line.strip()) for line in block)
        structured_count = 0
        pending: list[str] = []
        for line in block:
            stripped = line.strip()
            header = parse_modifier_header(stripped)
            if header:
                active_header = header
                continue
            if _parse_structured(stripped, data, requirements):
                structured_count += 1
                continue
            if active_header:
                data["modifiers"].append(_modifier(stripped, active_header))  # type: ignore[union-attr]
            elif re.search(r"\((rune|crafted|desecrated|implicit|hergestellt|entweiht|implizit)\)\s*$", stripped, re.I):
                data["modifiers"].append(_modifier(stripped))  # type: ignore[union-attr]
            else:
                pending.append(line)
        plausible_modifier_block = block_has_header or (structured_count == 0 and block_index > 1)
        for line in pending:
            if plausible_modifier_block:
                modifier = _modifier(line)
                data["modifiers"].append(modifier)  # type: ignore[union-attr]
                if modifier.normalized_key == "unknown":
                    data["unknown_lines"].append(line)  # type: ignore[union-attr]
            else:
                data["unknown_lines"].append(line)  # type: ignore[union-attr]
    return ParsedItem.model_validate(data)
