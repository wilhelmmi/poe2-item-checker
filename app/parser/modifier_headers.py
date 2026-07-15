import re
from dataclasses import dataclass

MODIFIER_HEADER_RE = re.compile(
    r'^\{\s*(?:(?P<qualifier>Crafted|Desecrated)\s+)?'
    r'(?P<kind>Prefix|Suffix|Implicit|Crafted|Desecrated|Rune|Unique|Granted Skill)'
    r'(?:\s+(?:Prefix|Suffix))?\s+Modifier'
    r'(?:\s+"(?P<name>[^"]+)")?(?:\s+\(Tier:\s*(?P<tier>\d+)\))?'
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
    kind = match.group("kind").lower()
    qualifier = (match.group("qualifier") or "").lower()
    affix_type = kind if kind in {"prefix", "suffix"} else None
    source = qualifier or ("explicit" if affix_type else kind.replace(" ", "_"))
    tags = tuple(tag.strip() for tag in (match.group("tags") or "").split(",") if tag.strip())
    tier = int(match.group("tier")) if match.group("tier") else None
    return ModifierHeader(source, affix_type, match.group("name"), tier, tags)
