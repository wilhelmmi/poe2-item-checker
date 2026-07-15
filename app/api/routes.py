from fastapi import APIRouter

from app.facts.engine import check_item_facts
from app.parser.service import parse_with_warnings
from app.schemas.checking import CheckItemResponse
from app.schemas.health import HealthResponse
from app.schemas.parsing import ParseItemRequest, ParseItemResponse, ParseWarning

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/items/parse", response_model=ParseItemResponse)
async def parse_item(request: ParseItemRequest) -> ParseItemResponse:
    return parse_with_warnings(request.raw_text)


@router.post("/items/check", response_model=CheckItemResponse)
async def check_item(request: ParseItemRequest) -> CheckItemResponse:
    parsed = parse_with_warnings(request.raw_text)
    blocking_codes = {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"}
    if any(warning.code in blocking_codes for warning in parsed.warnings):
        parsed.warnings.append(ParseWarning(
            code="assessment_skipped",
            message="Der lokale Faktencheck wurde wegen unvollständiger Parserdaten übersprungen.",
            lines=[],
            raw_lines=[],
        ))
        return CheckItemResponse(parse=parsed, assessment=None)
    return CheckItemResponse(parse=parsed, assessment=check_item_facts(parsed.item))
