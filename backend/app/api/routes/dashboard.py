from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.media import AudioStream, DolbyVisionMetadata, MediaFile, SubtitleStream, VideoStream
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _count_distinct_files(db: Session, query) -> int:
    return int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)


def _distribution(db: Session, query) -> dict[str, int]:
    return {str(name or "Unknown"): int(count) for name, count in db.execute(query)}


def _hdr_label():
    inferred_sdr = or_(
        VideoStream.base_hdr_format == "SDR",
        VideoStream.color_transfer.in_(("bt709", "bt470bg", "smpte170m", "gamma22", "gamma28")),
        (VideoStream.color_transfer.is_(None)) & (VideoStream.bit_depth.is_not(None)) & (VideoStream.bit_depth <= 8),
    )
    metadata_missing = (
        (VideoStream.base_hdr_format == "UNKNOWN")
        & (VideoStream.color_transfer.is_(None))
        & (
            (VideoStream.bit_depth >= 10)
            | VideoStream.color_primaries.in_(("bt2020", "bt2020nc", "bt2020c"))
        )
    )
    return case(
        (VideoStream.has_dolby_vision.is_(True), "Dolby Vision"),
        (VideoStream.has_hdr10_plus.is_(True), "HDR10+"),
        (VideoStream.base_hdr_format == "HDR10", "HDR10"),
        (VideoStream.base_hdr_format == "HLG", "HLG"),
        (inferred_sdr, "SDR"),
        (metadata_missing, "HDR metadata missing"),
        else_="Unknown",
    )


@router.get("/summary", response_model=DashboardSummary)
def read_summary(db: DatabaseSession, library_id: str | None = None) -> DashboardSummary:
    file_filter = [MediaFile.library_id == library_id] if library_id else []
    total_files = int(db.scalar(select(func.count(MediaFile.id)).where(*file_filter)) or 0)
    total_size_bytes = int(db.scalar(select(func.coalesce(func.sum(MediaFile.size_bytes), 0)).where(*file_filter)) or 0)
    scan_complete = int(db.scalar(select(func.count(MediaFile.id)).where(*file_filter, MediaFile.scan_status == "complete")) or 0)
    scan_failed = int(db.scalar(select(func.count(MediaFile.id)).where(*file_filter, MediaFile.scan_status == "failed")) or 0)

    video_base = select(MediaFile.id).join(VideoStream, VideoStream.media_file_id == MediaFile.id).where(*file_filter).distinct()
    hdr10 = _count_distinct_files(db, video_base.where(VideoStream.base_hdr_format == "HDR10"))
    hdr10_plus = _count_distinct_files(db, video_base.where(VideoStream.has_hdr10_plus.is_(True)))
    dolby_vision = _count_distinct_files(db, video_base.where(VideoStream.has_dolby_vision.is_(True)))

    profile_query = (
        select(DolbyVisionMetadata.profile, func.count(func.distinct(MediaFile.id)))
        .select_from(MediaFile)
        .join(VideoStream, VideoStream.media_file_id == MediaFile.id)
        .join(DolbyVisionMetadata, DolbyVisionMetadata.video_stream_id == VideoStream.id)
        .where(*file_filter)
        .group_by(DolbyVisionMetadata.profile)
        .order_by(DolbyVisionMetadata.profile)
    )
    profiles = _distribution(db, profile_query)

    audio_base = select(MediaFile.id).join(AudioStream, AudioStream.media_file_id == MediaFile.id).where(*file_filter).distinct()
    atmos = _count_distinct_files(db, audio_base.where(AudioStream.immersive_format == "DOLBY_ATMOS"))
    dts_x = _count_distinct_files(db, audio_base.where(AudioStream.immersive_format == "DTS_X"))

    hdr_label = _hdr_label()
    hdr_formats = _distribution(
        db,
        select(hdr_label.label("format"), func.count(func.distinct(MediaFile.id)))
        .select_from(MediaFile)
        .join(VideoStream, VideoStream.media_file_id == MediaFile.id)
        .where(*file_filter)
        .group_by(hdr_label),
    )
    video_codecs = _distribution(
        db,
        select(VideoStream.codec_name, func.count(func.distinct(MediaFile.id)))
        .select_from(MediaFile)
        .join(VideoStream, VideoStream.media_file_id == MediaFile.id)
        .where(*file_filter)
        .group_by(VideoStream.codec_name)
        .order_by(func.count(func.distinct(MediaFile.id)).desc()),
    )
    audio_label = case(
        (AudioStream.immersive_format == "DOLBY_ATMOS", "Dolby Atmos"),
        (AudioStream.immersive_format == "DTS_X", "DTS:X"),
        else_=AudioStream.codec_name,
    )
    audio_formats = _distribution(
        db,
        select(audio_label.label("format"), func.count(func.distinct(MediaFile.id)))
        .select_from(MediaFile)
        .join(AudioStream, AudioStream.media_file_id == MediaFile.id)
        .where(*file_filter)
        .group_by(audio_label)
        .order_by(func.count(func.distinct(MediaFile.id)).desc()),
    )
    resolution_label = case(
        (VideoStream.width >= 3800, "4K"),
        (VideoStream.width >= 1900, "1080p"),
        (VideoStream.width >= 1200, "720p"),
        (VideoStream.width.is_not(None), "SD"),
        else_="Unknown",
    )
    resolutions = _distribution(
        db,
        select(resolution_label.label("resolution"), func.count(func.distinct(MediaFile.id)))
        .select_from(MediaFile)
        .join(VideoStream, VideoStream.media_file_id == MediaFile.id)
        .where(*file_filter)
        .group_by(resolution_label),
    )

    hdr_missing = int(hdr_formats.get("HDR metadata missing", 0) + hdr_formats.get("Unknown", 0))
    no_subtitles = _count_distinct_files(
        db,
        select(MediaFile.id).where(*file_filter, ~MediaFile.subtitle_streams.any()).distinct(),
    )
    missing_audio_language = _count_distinct_files(
        db,
        select(MediaFile.id)
        .join(AudioStream, AudioStream.media_file_id == MediaFile.id)
        .where(*file_filter, AudioStream.language.is_(None))
        .distinct(),
    )

    return DashboardSummary(
        total_files=total_files,
        total_size_bytes=total_size_bytes,
        scan_complete=scan_complete,
        scan_failed=scan_failed,
        hdr10=hdr10,
        hdr10_plus=hdr10_plus,
        dolby_vision=dolby_vision,
        dolby_vision_profiles=profiles,
        atmos=atmos,
        dts_x=dts_x,
        hdr_formats=hdr_formats,
        video_codecs=video_codecs,
        audio_formats=audio_formats,
        resolutions=resolutions,
        library_health={
            "analyzed": scan_complete,
            "hdr_metadata_missing": hdr_missing,
            "failed_scans": scan_failed,
            "no_subtitles": no_subtitles,
            "missing_audio_language": missing_audio_language,
        },
    )
