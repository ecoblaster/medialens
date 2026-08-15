from __future__ import annotations

import re
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import utc_now
from app.models.enums import (
    DolbyVisionEnhancementLayer,
    FileScanStatus,
    ItemType,
    MediaKind,
    ScanFileStatus,
    ScanRunStatus,
)
from app.models.library import Library
from app.models.media import (
    AudioStream,
    DolbyVisionMetadata,
    MediaFile,
    MediaItem,
    ProbeSnapshot,
    SubtitleStream,
    VideoStream,
)
from app.models.scan import ScanFileResult, ScanRun
from app.services.media_paths import SUPPORTED_MEDIA_EXTENSIONS, is_supported_media_path
from app.services.normalizer import NormalizedMedia, normalize_probe
from app.services.probe import probe_media

# Kept as a public alias for existing callers and tests.
SUPPORTED_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS


class ScanValidationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def resolve_library_root(library: Library) -> Path:
    if library.source_type != "filesystem":
        raise ScanValidationError(
            "UNSUPPORTED_LIBRARY_SOURCE",
            "Scanning currently supports filesystem libraries only.",
            {"source_type": library.source_type},
        )
    if not library.enabled:
        raise ScanValidationError(
            "LIBRARY_DISABLED",
            "The selected library is disabled.",
            {"library_id": library.id},
        )
    try:
        root = Path(library.root_path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ScanValidationError(
            "LIBRARY_PATH_NOT_FOUND",
            "The library root path is not mounted or does not exist in the container.",
            {"root_path": library.root_path},
        ) from exc
    if not root.is_dir():
        raise ScanValidationError(
            "LIBRARY_PATH_NOT_DIRECTORY",
            "The configured library root is not a directory.",
            {"root_path": library.root_path},
        )
    return root


def resolve_media_path(library: Library, relative_path: str) -> tuple[Path, str]:
    root = resolve_library_root(library)
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ScanValidationError(
            "ABSOLUTE_PATH_NOT_ALLOWED",
            "Use a path relative to the configured library root.",
            {"relative_path": relative_path},
        )
    try:
        media_path = (root / requested).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ScanValidationError(
            "MEDIA_FILE_NOT_FOUND",
            "The requested media file does not exist in the container.",
            {"relative_path": relative_path},
        ) from exc
    if not media_path.is_relative_to(root):
        raise ScanValidationError(
            "PATH_OUTSIDE_LIBRARY",
            "The requested path resolves outside the configured library root.",
            {"relative_path": relative_path},
        )
    if not media_path.is_file():
        raise ScanValidationError(
            "NOT_A_FILE",
            "The requested path is not a file.",
            {"relative_path": relative_path},
        )
    if media_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ScanValidationError(
            "UNSUPPORTED_FILE_TYPE",
            "The requested file extension is not supported by this scanner version.",
            {"extension": media_path.suffix.lower()},
        )
    if not is_supported_media_path(media_path.relative_to(root)):
        raise ScanValidationError(
            "IGNORED_MEDIA_FILE",
            "The requested path matches a sample, temporary file, or "
            "release-group promotional clip.",
            {"relative_path": media_path.relative_to(root).as_posix()},
        )
    return media_path, media_path.relative_to(root).as_posix()


def discover_library_files(library: Library) -> list[tuple[Path, str]]:
    root = resolve_library_root(library)
    discovered: list[tuple[Path, str]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_file() and is_supported_media_path(relative):
            discovered.append((path, relative.as_posix()))
    return sorted(discovered, key=lambda item: item[1].casefold())


def _item_type(library: Library) -> str:
    if library.media_kind == MediaKind.MOVIES.value:
        return ItemType.MOVIE.value
    if library.media_kind == MediaKind.TV.value:
        return ItemType.EPISODE.value
    return ItemType.UNKNOWN.value


def _title_and_year(path: Path) -> tuple[str, int | None]:
    stem = path.stem
    match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", stem)
    year = int(match.group(1)) if match else None
    if match:
        stem = stem[: match.start()]
    title = re.sub(r"[._]+", " ", stem)
    return re.sub(r"\s+", " ", title).strip(" -[]()") or path.stem, year


def _apply_normalized(
    db: Session,
    media_file: MediaFile,
    normalized: NormalizedMedia,
) -> None:
    """Replace all normalized stream rows without violating stream indexes.

    SQLAlchemy can otherwise schedule replacement INSERT statements before the
    delete-orphan DELETE statements. SQLite then sees the old and new stream
    with the same (media_file_id, stream_index) at the same time and rejects
    the flush. Flush the removals first, then add the replacement rows.
    """
    media_file.video_streams.clear()
    media_file.audio_streams.clear()
    media_file.subtitle_streams.clear()
    db.flush()

    video_indexes: set[int] = set()
    for data in normalized.videos:
        if data.stream_index in video_indexes:
            continue
        video_indexes.add(data.stream_index)
        stream = VideoStream(
            stream_index=data.stream_index,
            codec_name=data.codec_name,
            codec_profile=data.codec_profile,
            width=data.width,
            height=data.height,
            pixel_format=data.pixel_format,
            bit_depth=data.bit_depth,
            bitrate=data.bitrate,
            frame_rate_num=data.frame_rate_num,
            frame_rate_den=data.frame_rate_den,
            color_primaries=data.color_primaries,
            color_transfer=data.color_transfer,
            color_matrix=data.color_matrix,
            base_hdr_format=data.base_hdr_format,
            has_hdr10_plus=data.has_hdr10_plus,
            has_dolby_vision=data.has_dolby_vision,
            language=data.language,
            title=data.title,
            is_default=data.is_default,
            is_forced=data.is_forced,
        )
        if data.dolby_vision:
            stream.dolby_vision = DolbyVisionMetadata(
                profile=data.dolby_vision.profile,
                level=data.dolby_vision.level,
                compatibility_id=data.dolby_vision.compatibility_id,
                bl_present=data.dolby_vision.bl_present,
                el_present=data.dolby_vision.el_present,
                rpu_present=data.dolby_vision.rpu_present,
                el_type=data.dolby_vision.el_type,
                detected_by=data.dolby_vision.detected_by,
            )
        media_file.video_streams.append(stream)

    audio_indexes: set[int] = set()
    for data in normalized.audios:
        if data.stream_index in audio_indexes:
            continue
        audio_indexes.add(data.stream_index)
        media_file.audio_streams.append(
            AudioStream(
                stream_index=data.stream_index,
                codec_name=data.codec_name,
                codec_profile=data.codec_profile,
                channels=data.channels,
                channel_layout=data.channel_layout,
                sample_rate=data.sample_rate,
                bit_depth=data.bit_depth,
                bitrate=data.bitrate,
                immersive_format=data.immersive_format,
                language=data.language,
                title=data.title,
                is_default=data.is_default,
                is_forced=data.is_forced,
                is_commentary=data.is_commentary,
            )
        )

    subtitle_indexes: set[int] = set()
    for data in normalized.subtitles:
        if data.stream_index in subtitle_indexes:
            continue
        subtitle_indexes.add(data.stream_index)
        media_file.subtitle_streams.append(
            SubtitleStream(
                stream_index=data.stream_index,
                codec_name=data.codec_name,
                format_class=data.format_class,
                language=data.language,
                title=data.title,
                is_default=data.is_default,
                is_forced=data.is_forced,
                is_hearing_impaired=data.is_hearing_impaired,
            )
        )


def _new_scan_run(
    db: Session,
    library: Library,
    *,
    mode: str,
    status: str,
    requested_relative_path: str | None = None,
) -> ScanRun:
    scan = ScanRun(
        library_id=library.id,
        mode=mode,
        status=status,
        requested_relative_path=requested_relative_path,
        started_at=utc_now() if status == ScanRunStatus.RUNNING.value else None,
        app_version=settings.app_version,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def _needs_metadata_refresh(media_file: MediaFile) -> bool:
    """Return whether an unchanged file needs newer scanner metadata.

    Profile 7 rows created before RPU analysis was added contain ``UNKNOWN``
    (or occasionally ``NONE``) for the enhancement-layer type.  Treat those
    rows as stale so a regular library scan upgrades them without forcing a
    costly re-probe of every unchanged file.
    """
    classified_el_types = {
        DolbyVisionEnhancementLayer.FEL.value,
        DolbyVisionEnhancementLayer.MEL.value,
    }
    return any(
        stream.dolby_vision is not None
        and stream.dolby_vision.profile == "7"
        and stream.dolby_vision.el_type not in classified_el_types
        for stream in media_file.video_streams
    )


def _scan_file(
    db: Session,
    scan_run: ScanRun,
    library: Library,
    media_path: Path,
    canonical_relative: str,
    *,
    force: bool,
) -> None:
    started = time.monotonic()
    existing_file = db.scalar(
        select(MediaFile).where(
            MediaFile.library_id == library.id,
            MediaFile.relative_path == canonical_relative,
        )
    )
    stat = media_path.stat()
    if (
        existing_file is not None
        and not force
        and existing_file.scan_status == FileScanStatus.COMPLETE.value
        and existing_file.size_bytes == stat.st_size
        and existing_file.mtime_ns == stat.st_mtime_ns
        and not _needs_metadata_refresh(existing_file)
    ):
        scan_run.files_skipped += 1
        scan_run.file_results.append(
            ScanFileResult(
                media_file_id=existing_file.id,
                relative_path=canonical_relative,
                status=ScanFileStatus.UNCHANGED.value,
                metadata_changed=False,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return

    probes = probe_media(media_path)
    normalized = normalize_probe(probes.ffprobe, probes.mediainfo, media_path)
    media_file = existing_file
    if media_file is None:
        title, year = _title_and_year(media_path)
        item = MediaItem(
            library_id=library.id,
            item_type=_item_type(library),
            title=title,
            year=year,
        )
        media_file = MediaFile(
            library_id=library.id,
            media_item=item,
            relative_path=canonical_relative,
            filename=media_path.name,
        )
        # Adding only the parent MediaItem is not sufficient in every SQLAlchemy
        # relationship state. Explicitly persist both rows before stream metadata
        # is attached so automatic single-file imports cannot report success while
        # leaving MediaFile transient.
        db.add_all([item, media_file])
        db.flush()

    media_file.filename = media_path.name
    media_file.container = normalized.container
    media_file.size_bytes = stat.st_size
    media_file.duration_ms = normalized.duration_ms
    media_file.overall_bitrate = normalized.overall_bitrate
    media_file.mtime_ns = stat.st_mtime_ns
    media_file.scan_status = FileScanStatus.COMPLETE.value
    media_file.last_error = None
    media_file.last_scanned_at = utc_now()
    _apply_normalized(db, media_file, normalized)
    db.flush()
    media_file.probe_snapshots.extend(
        [
            ProbeSnapshot(
                scan_run_id=scan_run.id,
                tool_name="ffprobe",
                tool_version=probes.ffprobe_version,
                payload_json=probes.ffprobe,
            ),
            ProbeSnapshot(
                scan_run_id=scan_run.id,
                tool_name="mediainfo",
                tool_version=probes.mediainfo_version,
                payload_json=probes.mediainfo,
            ),
        ]
    )
    scan_run.files_analyzed += 1
    scan_run.file_results.append(
        ScanFileResult(
            media_file_id=media_file.id,
            relative_path=canonical_relative,
            status=ScanFileStatus.ANALYZED.value,
            metadata_changed=True,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
    )


def _record_file_failure(
    db: Session,
    *,
    scan_id: str,
    library_id: str,
    relative_path: str,
    existing_file_id: str | None,
    started: float,
    error: Exception,
) -> None:
    db.rollback()
    scan_run = db.get(ScanRun, scan_id)
    if scan_run is None:
        raise error
    existing_file = db.get(MediaFile, existing_file_id) if existing_file_id else None
    if existing_file is None:
        existing_file = db.scalar(
            select(MediaFile).where(
                MediaFile.library_id == library_id,
                MediaFile.relative_path == relative_path,
            )
        )
    if existing_file is not None:
        existing_file.scan_status = FileScanStatus.FAILED.value
        existing_file.last_error = str(error)
        existing_file.last_scanned_at = utc_now()
    scan_run.files_failed += 1
    scan_run.file_results.append(
        ScanFileResult(
            media_file_id=existing_file.id if existing_file is not None else None,
            relative_path=relative_path,
            status=ScanFileStatus.FAILED.value,
            metadata_changed=False,
            duration_ms=round((time.monotonic() - started) * 1000),
            error_message=str(error),
        )
    )
    db.commit()


def scan_single_file(
    db: Session,
    library: Library,
    relative_path: str,
    *,
    force: bool = False,
) -> ScanRun:
    media_path, canonical_relative = resolve_media_path(library, relative_path)
    scan_run = _new_scan_run(
        db,
        library,
        mode="single_file",
        status=ScanRunStatus.RUNNING.value,
        requested_relative_path=canonical_relative,
    )
    scan_run.files_discovered = 1
    started = time.monotonic()
    existing = db.scalar(
        select(MediaFile).where(
            MediaFile.library_id == library.id,
            MediaFile.relative_path == canonical_relative,
        )
    )
    existing_id = existing.id if existing else None
    try:
        _scan_file(
            db,
            scan_run,
            library,
            media_path,
            canonical_relative,
            force=force,
        )
        db.flush()

        # A scan is never allowed to become completed unless the MediaFile row is
        # visible in the current transaction. This catches missing session/cascade
        # registration before the success state is committed.
        persisted_file_id = db.scalar(
            select(MediaFile.id).where(
                MediaFile.library_id == library.id,
                MediaFile.relative_path == canonical_relative,
            )
        )
        if persisted_file_id is None:
            raise RuntimeError(
                "The scanner analyzed the file but did not persist its MediaFile record."
            )

        scan_run.status = ScanRunStatus.COMPLETED.value
        scan_run.completed_at = utc_now()
        library.last_scan_at = scan_run.completed_at
        db.commit()
    except Exception as exc:
        _record_file_failure(
            db,
            scan_id=scan_run.id,
            library_id=library.id,
            relative_path=canonical_relative,
            existing_file_id=existing_id,
            started=started,
            error=exc,
        )
        scan_run = db.get(ScanRun, scan_run.id)
        if scan_run is None:
            raise
        scan_run.status = ScanRunStatus.FAILED.value
        scan_run.error_message = str(exc)
        scan_run.completed_at = utc_now()
        db.commit()
    return db.get(ScanRun, scan_run.id)


def queue_library_scan(db: Session, library: Library) -> ScanRun:
    resolve_library_root(library)
    return _new_scan_run(
        db,
        library,
        mode="full",
        status=ScanRunStatus.QUEUED.value,
    )
