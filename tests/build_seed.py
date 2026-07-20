import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.builds.registry import list_builtin_builds
from app.db.models import Build


def seed_builtin_builds(db: Session) -> None:
    for context in list_builtin_builds():
        db.add(Build(
            id=str(uuid.uuid4()), fingerprint=f"builtin:{context.build_id}", citations=[],
            created_at=datetime.now(timezone.utc), **context.model_dump(mode="json"),
        ))
    db.commit()
