import json
from functools import lru_cache
from importlib.resources import files

from app.facts.schemas import FactsConfig


@lru_cache
def load_facts_config() -> FactsConfig:
    path = files("app").joinpath("rules/facts-v1.json")
    return FactsConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


FACTS_CONFIG = load_facts_config()
