import hashlib
import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.builds.registry import BuildContext, get_builtin_build, list_builtin_builds
from app.builds.schemas import BuildAnalysis, BuildCitation
from app.db.models import AppPreference, BuildPreview, CustomBuild


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


def row_context(row: CustomBuild) -> BuildContext:
    return BuildContext(
        build_id=row.build_id, version=row.version, name=row.name, author=row.author,
        source_url=row.source_url, source_variant=row.source_variant, archetype=row.archetype,
        core_skills=tuple(row.core_skills), offensive_priorities=tuple(row.offensive_priorities),
        defensive_priorities=tuple(row.defensive_priorities), item_priorities=tuple(row.item_priorities),
        low_value_stats=tuple(row.low_value_stats), constraints=tuple(row.constraints),
    )


def list_all_builds(db: Session) -> tuple[BuildContext, ...]:
    custom = db.scalars(select(CustomBuild).order_by(CustomBuild.created_at)).all()
    return (*list_builtin_builds(), *(row_context(row) for row in custom))


def get_any_build(db: Session, build_id: str) -> BuildContext:
    try:
        return get_builtin_build(build_id)
    except ValueError:
        row = db.scalar(select(CustomBuild).where(CustomBuild.build_id == build_id))
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


def confirm_preview(db: Session, preview_id: str) -> CustomBuild:
    row = db.get(BuildPreview, preview_id)
    if row is None:
        raise ValueError("preview_not_found")
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if expires <= datetime.now(timezone.utc):
        raise ValueError("preview_expired")
    if row.confirmed_build_id:
        existing = db.scalar(select(CustomBuild).where(CustomBuild.build_id == row.confirmed_build_id))
        if existing:
            return existing
    existing = db.scalar(select(CustomBuild).where(
        CustomBuild.source_url == row.source_url, CustomBuild.fingerprint == row.fingerprint))
    if existing:
        row.confirmed_build_id = existing.build_id
        db.commit()
        return existing
    version = (db.scalar(select(func.max(CustomBuild.version)).where(
        CustomBuild.source_url == row.source_url)) or 0) + 1
    prefix = hashlib.sha256(row.source_url.encode()).hexdigest()[:16]
    build_id = f"custom-{prefix}-v{version}"
    if any(build.build_id == build_id for build in list_builtin_builds()):
        raise ValueError("build_id_collision")
    data = BuildAnalysis.model_validate(row.analysis)
    custom = CustomBuild(build_id=build_id, version=version, source_url=row.source_url,
        fingerprint=row.fingerprint, citations=row.citations, **data.model_dump(exclude={"uncertainties"}))
    db.add(custom)
    row.confirmed_build_id = build_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(CustomBuild).where(
            CustomBuild.source_url == row.source_url,
            CustomBuild.fingerprint == row.fingerprint,
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


def get_active(db: Session) -> str:
    pref = db.get(AppPreference, "active_build_id")
    candidate = pref.value if pref else list_builtin_builds()[-1].build_id
    try:
        get_any_build(db, candidate)
    except ValueError:
        return list_builtin_builds()[-1].build_id
    return candidate


def set_active(db: Session, build_id: str) -> str:
    get_any_build(db, build_id)
    row = db.get(AppPreference, "active_build_id")
    if row:
        row.value = build_id
    else:
        db.add(AppPreference(key="active_build_id", value=build_id))
    db.commit()
    return build_id
