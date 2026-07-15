from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.db.models import Base, Item, Modifier
from app.db.session import enable_sqlite_foreign_keys, engine


def test_sqlite_foreign_keys_are_enabled() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_item_delete_cascades_to_modifiers(tmp_path: Path) -> None:
    database = tmp_path / "cascade.db"
    isolated_engine = create_engine(f"sqlite:///{database}")
    event.listen(isolated_engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(isolated_engine)
    with Session(isolated_engine) as session:
        item = Item(raw_text="test")
        item.modifiers.append(Modifier(source="explicit", raw_text="unknown"))
        session.add(item)
        session.commit()
        item_id = item.id
        session.delete(item)
        session.commit()
        assert session.query(Modifier).filter_by(item_id=item_id).count() == 0
