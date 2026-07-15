from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import CharacterProfile, Evaluation, Item, SaleRecord


def test_character_profile_defaults() -> None:
    profile = CharacterProfile(name="Chaos DoT Lich")
    assert profile.build_stage == "early_endgame"
    assert profile.resistance_cap == 75
    assert profile.life is None


def test_item_validates_from_orm_attributes_and_parses_uuid() -> None:
    item_id = uuid4()
    source = SimpleNamespace(
        id=str(item_id),
        raw_text="Item Class: Wands",
        unknown_lines=[],
        item_class="Wands",
        rarity="Normal",
        name="Withered Wand",
        base_type="Withered Wand",
        required_level=None,
        required_strength=None,
        required_dexterity=None,
        required_intelligence=None,
        item_level=None,
        quality=None,
        sockets=[],
        armour=None,
        armour_augmented=False,
        evasion=None,
        evasion_augmented=False,
        energy_shield=None,
        energy_shield_augmented=False,
        spirit=None,
        granted_skill=None,
        identified=True,
        corrupted=False,
        created_at=Item(raw_text="seed").created_at,
        modifiers=[],
    )
    assert Item.model_validate(source).id == item_id


def test_evaluation_scores_and_recommendations_are_nullable() -> None:
    evaluation = Evaluation(item_id=uuid4(), character_id=1)
    assert evaluation.build_fit_score is None
    assert evaluation.trade_potential_score is None
    assert evaluation.upgrade_recommendation is None


def test_sale_record_preserves_decimal_amounts() -> None:
    sale = SaleRecord(item_id=uuid4(), listed_amount="1.2500")
    assert sale.listed_amount == Decimal("1.2500")
