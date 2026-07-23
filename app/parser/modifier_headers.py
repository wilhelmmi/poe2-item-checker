import re
from dataclasses import dataclass

MODIFIER_HEADER_RE = re.compile(
    r'^\{\s*(?:(?P<qualifier>Crafted|Desecrated|Hergestellt(?:er|e|es)?|Entweiht(?:er|e|es)?)\s+)?'
    r'(?P<kind>Prefix|Präfix|Suffix|Implicit|Implizit(?:er|e|es)?|Crafted|Hergestellt(?:er|e|es)?|'
    r'Desecrated|Entweiht(?:er|e|es)?|Rune|Runen|Unique|Einzigartig(?:er|e|es)?|Granted Skill|Gewährte Fertigkeit)'
    r'(?:[\s-]+(?:Prefix|Präfix|Suffix))?[\s-]+(?:Modifier|Modifikator)'
    r'(?:\s+"(?P<name>[^"]+)")?(?:\s+\((?:Tier|Rang):\s*(?P<tier>\d+)\))?'
    r'(?:\s+[—-]\s+(?P<tags>[^}]+))?\s*\}$',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ModifierHeader:
    source: str = "explicit"
    affix_type: str | None = None
    name: str | None = None
    tier: int | None = None
    tags: tuple[str, ...] = ()


def parse_modifier_header(line: str) -> ModifierHeader | None:
    """Parse a complete modifier header using the parser's public canonical grammar."""
    match = MODIFIER_HEADER_RE.fullmatch(line)
    if not match:
        return None
    aliases = {
        "präfix": "prefix", "implizit": "implicit", "impliziter": "implicit",
        "implizite": "implicit", "implizites": "implicit", "hergestellt": "crafted",
        "hergestellter": "crafted", "hergestellte": "crafted", "hergestelltes": "crafted",
        "entweiht": "desecrated", "entweihter": "desecrated", "entweihte": "desecrated",
        "entweihtes": "desecrated", "runen": "rune", "einzigartig": "unique",
        "einzigartiger": "unique", "einzigartige": "unique", "einzigartiges": "unique",
        "gewährte fertigkeit": "granted_skill",
    }
    raw_kind = match.group("kind").lower()
    kind = aliases.get(raw_kind, raw_kind)
    raw_qualifier = (match.group("qualifier") or "").lower()
    qualifier = aliases.get(raw_qualifier, raw_qualifier)
    affix_type = kind if kind in {"prefix", "suffix"} else None
    source = qualifier or ("explicit" if affix_type else kind.replace(" ", "_"))
    tags = tuple(tag.strip() for tag in (match.group("tags") or "").split(",") if tag.strip())
    tier = int(match.group("tier")) if match.group("tier") else None
    return ModifierHeader(source, affix_type, match.group("name"), tier, tags)
