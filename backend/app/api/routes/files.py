from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.media import AudioStream, DolbyVisionMetadata, MediaFile, MediaItem, VideoStream
from app.schemas.media import MediaFileRead

router = APIRouter(prefix="/files", tags=["media files"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _file_query():
    return select(MediaFile).options(
        selectinload(MediaFile.media_item),
        selectinload(MediaFile.video_streams).selectinload(VideoStream.dolby_vision),
        selectinload(MediaFile.audio_streams),
        selectinload(MediaFile.subtitle_streams),
    )


def _hdr_metadata_missing_condition():
    return (
        (VideoStream.base_hdr_format == "UNKNOWN")
        & (VideoStream.color_transfer.is_(None))
        & (
            (VideoStream.bit_depth >= 10)
            | VideoStream.color_primaries.in_(("bt2020", "bt2020nc", "bt2020c"))
        )
    )


@router.get("", response_model=list[MediaFileRead])
def list_files(
    db: DatabaseSession,
    library_id: str | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=300)] = None,
    dolby_vision_profile: str | None = None,
    has_hdr10_plus: bool | None = None,
    immersive_format: str | None = None,
    codec_name: str | None = None,
    health: Literal["hdr_metadata_missing", "failed_scans", "no_subtitles", "missing_audio_language"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MediaFile]:
    query = _file_query().order_by(MediaFile.relative_path).offset(offset).limit(limit)
    if library_id:
        query = query.where(MediaFile.library_id == library_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(MediaFile.media_item).where(
            or_(
                MediaFile.filename.ilike(pattern),
                MediaFile.relative_path.ilike(pattern),
                MediaItem.title.ilike(pattern),
            )
        )
    if codec_name:
        query = query.where(MediaFile.video_streams.any(VideoStream.codec_name == codec_name.lower()))
    if has_hdr10_plus is not None:
        query = query.where(MediaFile.video_streams.any(VideoStream.has_hdr10_plus == has_hdr10_plus))
    if immersive_format:
        query = query.where(MediaFile.audio_streams.any(AudioStream.immersive_format == immersive_format.upper()))
    if dolby_vision_profile:
        query = query.where(
            MediaFile.video_streams.any(
                VideoStream.dolby_vision.has(DolbyVisionMetadata.profile == dolby_vision_profile)
            )
        )
    if health == "hdr_metadata_missing":
        query = query.where(MediaFile.video_streams.any(_hdr_metadata_missing_condition()))
    elif health == "failed_scans":
        query = query.where(MediaFile.scan_status == "failed")
    elif health == "no_subtitles":
        query = query.where(~MediaFile.subtitle_streams.any())
    elif health == "missing_audio_language":
        query = query.where(MediaFile.audio_streams.any(AudioStream.language.is_(None)))
    return list(db.scalars(query).unique().all())


@router.get("/{file_id}", response_model=MediaFileRead)
def read_file(file_id: str, db: DatabaseSession) -> MediaFile:
    media_file = db.scalar(_file_query().where(MediaFile.id == file_id))
    if media_file is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEDIA_FILE_NOT_FOUND",
                "message": "The requested media file does not exist.",
                "details": {"file_id": file_id},
            },
        )
    return media_file
