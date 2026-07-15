from pydantic import BaseModel

from app.facts.schemas import FactsCheck
from app.schemas.parsing import ParseItemResponse


class CheckItemResponse(BaseModel):
    parse: ParseItemResponse
    assessment: FactsCheck | None
