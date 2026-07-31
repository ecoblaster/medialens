from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import event, select
from sqlalchemy.orm import Session, selectinload

from app.models.media import MediaFile, MediaItem, VideoStream

_AFFECTED_LIBRARIES = "medialens_media_version_libraries"
_SYNCHRONIZING = "medialens_media_version_syncing"

_RELEASE_TOKEN = re.compile(
    r"\b(?:2160p|4k|1080p|1080i|720p|576p|480p|uhd|bluray|blu-ray|bdrip|"
    r"web[ ._-]?dl|webrip|hdtv|remux|hdr10\+?|hdr|hlg|dolby[ ._-]?vision|"
    r"dovi|dv|x26[45]|h\.?26[45]|hevc|av1|vc-?1|mpeg-?2|proper|repack|"
    r"extended|unrated|theatrical|director'?s[ ._-]?cut|imax)\b.*$",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title_identity(title: str) -> str:
    """Return a stable comparison key while preserving the stored display title."""
    cleaned = _RELEASE_TOKEN.sub("", title).casefold()
    return _NON_ALNUM.sub(" ", cleaned).strip()


def _item_identity(item: MediaItem) -> tuple[str, str, int | None, int | None, int | None]:
    return (
        item.item_type,
        normalize_title_identity(item.title),
        item.year,
        item.season_number,
        item.episode_number,
    )


def _primary_video(media_file: MediaFile) -> VideoStream | None:
    if not media_file.video_streams:
        return None
    return max(
        media_file.video_streams,
        key=lambda stream: (
            stream.is_default,
            (stream.width or 0) * (stream.height or 0),
            stream.bitrate or 0,
        ),
    )


def _display_resolution(media_file: MediaFile) -> str:
    video = _primary_video(media_file)
    if video is None:
        return "Unknown resolution"
    height = video.height or 0
    width = video.width or 0
    if height >= 2000 or width >= 3800:
        return "4K"
    if height >= 1000 or width >= 1900:
        return "1080p"
    if height >= 700 or width >= 1200:
        return "720p"
    if height:
        return f"{height}p"
    return "Unknown resolution"


def _display_hdr(media_file: MediaFile) -> str:
    video = _primary_video(media_file)
    if video is None:
        return ""
    if video.has_dolby_vision:
        profile = video.dolby_vision.profile if video.dolby_vision else None
        return f"Dolby Vision P{profile}" if profile else "Dolby Vision"
    if video.has_hdr10_plus:
        return "HDR10+"
    if video.base_hdr_format == "HDR10":
        return "HDR10"
    if video.base_hdr_format == "HLG":
        return "HLG"
    if video.base_hdr_format == "SDR":
        return "SDR"
    return "HDR metadata unknown" if video.base_hdr_format == "UNKNOWN" else video.base_hdr_format


def build_version_label(media_file: MediaFile) -> str:
    return " · ".join(
        part
        for part in (_display_resolution(media_file), _display_hdr(media_file))
        if part
    )


def _primary_rank(media_file: MediaFile) -> tuple[int, int, int, int, str]:
    video = _primary_video(media_file)
    return (
        (video.width or 0) * (video.height or 0) if video else 0,
        video.bitrate or 0 if video else 0,
        media_file.overall_bitrate or 0,
        media_file.size_bytes,
        media_file.relative_path.casefold(),
    )


def _preferred_item(items: Iterable[MediaItem]) -> MediaItem:
    return min(
        items,
        key=lambda item: (
            0 if item.external_id else 1,
            0 if item.external_guid else 1,
            len(item.title),
            item.created_at,
            item.id,
        ),
    )


def synchronize_library_versions(session: Session, library_id: str) -> None:
    """Merge duplicate title rows and label every physical media version."""
    items = list(
        session.scalars(
            select(MediaItem)
            .where(MediaItem.library_id == library_id)
            .options(
                selectinload(MediaItem.files)
                .selectinload(MediaFile.video_streams)
                .selectinload(VideoStream.dolby_vision),
                selectinload(MediaItem.children),
            )
        )
        .unique()
        .all()
    )

    grouped: dict[
        tuple[str, str, int | None, int | None, int | None], list[MediaItem]
    ] = defaultdict(list)
    for item in items:
        identity = _item_identity(item)
        if identity[1]:
            grouped[identity].append(item)

    for matching_items in grouped.values():
        canonical = _preferred_item(matching_items)
        all_files: list[MediaFile] = []

        for item in matching_items:
            all_files.extend(item.files)
            if item is canonical:
                continue
            for child in list(item.children):
                child.parent = canonical
            for media_file in list(item.files):
                media_file.media_item = canonical
            session.delete(item)

        if not all_files:
            continue

        primary = max(all_files, key=_primary_rank)
        for media_file in all_files:
            label = build_version_label(media_file)
            if media_file.version_label != label:
                media_file.version_label = label
            should_be_primary = media_file is primary
            if media_file.is_primary != should_be_primary:
                media_file.is_primary = should_be_primary


@event.listens_for(Session, "before_flush")
def _remember_affected_libraries(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    if session.info.get(_SYNCHRONIZING):
        return
    library_ids = session.info.setdefault(_AFFECTED_LIBRARIES, set())
    for obj in session.new.union(session.dirty):
        if isinstance(obj, MediaFile):
            library_id = obj.library_id or (
                obj.media_item.library_id if obj.media_item else None
            )
            if library_id:
                library_ids.add(library_id)
        elif isinstance(obj, MediaItem) and obj.library_id:
            library_ids.add(obj.library_id)


@event.listens_for(Session, "after_flush_postexec")
def _group_and_label_versions(session: Session, _flush_context: object) -> None:
    if session.info.get(_SYNCHRONIZING):
        return
    library_ids = session.info.pop(_AFFECTED_LIBRARIES, set())
    if not library_ids:
        return

    session.info[_SYNCHRONIZING] = True
    try:
        for library_id in sorted(library_ids):
            synchronize_library_versions(session, library_id)
    finally:
        session.info[_SYNCHRONIZING] = False
