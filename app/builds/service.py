import hashlib
import ipaddress
import json
import re
from threading import RLock
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.builds.registry import BuildContext
from app.builds.schemas import BuildAnalysis, BuildCitation
from app.db.models import AppPreference, Build, BuildPreview


_build_mutation_lock = RLock()


def canonicalize_source_url(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("invalid_build_url")
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").rstrip(".").lower()
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError
        if parsed.fragment or host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", host):
                raise ValueError
        else:
            if not address.is_global:
                raise ValueError
        port = parsed.port
        netloc = host if port is None else f"{host}:{port}"
        canonical = urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, ""))
        if len(canonical) > 2048:
            raise ValueError
        return canonical
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid_build_url") from exc


def fingerprint(analysis: BuildAnalysis) -> str:
    payload = json.dumps(analysis.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def row_context(row: Build) -> BuildContext:
    return BuildContext(
        build_id=row.build_id, version=row.version, name=row.name, author=row.author,
        source_url=row.source_url, source_variant=row.source_variant, archetype=row.archetype,
        core_skills=tuple(row.core_skills), offensive_priorities=tuple(row.offensive_priorities),
        defensive_priorities=tuple(row.defensive_priorities), item_priorities=tuple(row.item_priorities),
        low_value_stats=tuple(row.low_value_stats), constraints=tuple(row.constraints),
    )


def list_all_builds(db: Session) -> tuple[BuildContext, ...]:
    rows = db.scalars(select(Build).order_by(Build.created_at, Build.build_id)).all()
    return tuple(row_context(row) for row in rows)


def get_any_build(db: Session, build_id: str) -> BuildContext:
    row = db.scalar(select(Build).where(Build.build_id == build_id))
    if row is None:
        raise ValueError("unknown_build")
    return row_context(row)


def create_preview(db: Session, url: str, analysis: BuildAnalysis,
                   citations: list[BuildCitation], provider: str, model: str) -> BuildPreview:
    db.execute(delete(BuildPreview).where(BuildPreview.expires_at < datetime.now(timezone.utc)))
    row = BuildPreview(source_url=url, analysis=analysis.model_dump(),
        citations=[citation.model_dump(mode="json") for citation in citations],
        fingerprint=fingerprint(analysis), provider=provider, model=model,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _confirm_preview(db: Session, preview_id: str) -> Build:
    row = db.get(BuildPreview, preview_id)
    if row is None:
        raise ValueError("preview_not_found")
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if expires <= datetime.now(timezone.utc):
        raise ValueError("preview_expired")
    if row.confirmed_build_id:
        existing = db.scalar(select(Build).where(Build.build_id == row.confirmed_build_id))
        if existing:
            return existing
    existing = db.scalar(select(Build).where(
        Build.source_url == row.source_url, Build.fingerprint == row.fingerprint))
    if existing:
        row.confirmed_build_id = existing.build_id
        db.commit()
        return existing
    version = (db.scalar(select(func.max(Build.version)).where(
        Build.source_url == row.source_url)) or 0) + 1
    prefix = hashlib.sha256(row.source_url.encode()).hexdigest()[:16]
    build_id = f"custom-{prefix}-v{version}"
    if db.scalar(select(Build).where(Build.build_id == build_id)) is not None:
        raise ValueError("build_id_collision")
    data = BuildAnalysis.model_validate(row.analysis)
    custom = Build(build_id=build_id, version=version, source_url=row.source_url,
        fingerprint=row.fingerprint, citations=row.citations, **data.model_dump(exclude={"uncertainties"}))
    db.add(custom)
    row.confirmed_build_id = build_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Build).where(
            Build.source_url == row.source_url,
            Build.fingerprint == row.fingerprint,
        ))
        if existing is not None:
            refreshed = db.get(BuildPreview, preview_id)
            if refreshed is not None:
                refreshed.confirmed_build_id = existing.build_id
                db.commit()
            return existing
        raise ValueError("concurrent_build_confirmation") from None
    db.refresh(custom)
    return custom


def confirm_preview(db: Session, preview_id: str) -> Build:
    with _build_mutation_lock:
        return _confirm_preview(db, preview_id)


def get_active(db: Session) -> str | None:
    pref = db.get(AppPreference, "active_build_id")
    if pref:
        try:
            get_any_build(db, pref.value)
            return pref.value
        except ValueError:
            pass
    first = db.scalar(select(Build).order_by(Build.created_at, Build.build_id))
    return first.build_id if first else None


def set_active(db: Session, build_id: str) -> str:
    with _build_mutation_lock:
        get_any_build(db, build_id)
        row = db.get(AppPreference, "active_build_id")
        if row:
            row.value = build_id
        else:
            db.add(AppPreference(key="active_build_id", value=build_id))
        db.commit()
        return build_id


def delete_custom_build(db: Session, build_id: str) -> str | None:
    """Delete any build and return a deterministic active build, or None."""
    with _build_mutation_lock:
        custom = db.scalar(select(Build).where(Build.build_id == build_id))
        if custom is None:
            raise ValueError("unknown_build")

        active = db.get(AppPreference, "active_build_id")
        active_build_id = get_active(db)
        db.execute(
            BuildPreview.__table__.update()
            .where(BuildPreview.confirmed_build_id == build_id)
            .values(confirmed_build_id=None)
        )
        db.delete(custom)
        db.flush()
        if active_build_id == build_id:
            next_build = db.scalar(select(Build).order_by(Build.created_at, Build.build_id))
            active_build_id = next_build.build_id if next_build else None
            if active_build_id is None:
                if active is not None:
                    db.delete(active)
            elif active is None:
                db.add(AppPreference(key="active_build_id", value=active_build_id))
            else:
                active.value = active_build_id
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return active_build_id
