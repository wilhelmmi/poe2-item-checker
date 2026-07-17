from typing import Protocol

from app.evaluation.schemas import EvaluationResult
from app.evaluation.schemas import EvaluationInput


class EvaluationProviderError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int = 502) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


class EvaluationProvider(Protocol):
    name: str
    model: str

    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult: ...
