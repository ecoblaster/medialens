from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.media import MediaFile, VideoStream
from app.schemas.compatibility import (
    CompatibilityFileListRead,
    CompatibilitySummaryRead,
    DeviceProfileRead,
    FileCompatibilityRead,
)
from app.services.compatibility import (
    DeviceProfile,
    evaluate_file,
    get_device_profile,
    list_device_profiles,
)
from app.services.google_tv_compatibility import (
    get_google_tv_device_profile,
    list_google_tv_device_profiles,
)
from app.services.homatics_compatibility import (
    get_homatics_device_profile,
    list_homatics_device_profiles,
)
from app.services.xiaomi_compatibility import (
    get_xiaomi_device_profile,
    list_xiaomi_device_profiles,
)

router = APIRouter(prefix="/compatibility", tags=["hardware compatibility"])
DatabaseSession = Annotated[Session, Depends(get_db)]
OutcomeFilter = Literal[
    "direct_play",
    "remux",
    "audio_transcode",
    "video_transcode",
    "unsupported",
    "unknown",
]


def _media_query():
    return select(MediaFile).options(
        selectinload(MediaFile.media_item),
        selectinload(MediaFile.video_streams).selectinload(VideoStream.dolby_vision),
        selectinload(MediaFile.audio_streams),
        selectinload(MediaFile.subtitle_streams),
    )


def _all_device_profiles() -> list[DeviceProfile]:
    return [
        *list_device_profiles(),
        *list_google_tv_device_profiles(),
        *list_homatics_device_profiles(),
        *list_xiaomi_device_profiles(),
    ]


def _profile_or_404(device_id: str) -> DeviceProfile:
    profile = (
        get_device_profile(device_id)
        or get_google_tv_device_profile(device_id)
        or get_homatics_device_profile(device_id)
        or get_xiaomi_device_profile(device_id)
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_PROFILE_NOT_FOUND",
                "message": "The requested hardware compatibility profile does not exist.",
                "details": {"device_id": device_id},
            },
        )
    return profile


@router.get("/devices", response_model=list[DeviceProfileRead])
def devices() -> list[DeviceProfileRead]:
    return [profile.read_model() for profile in _all_device_profiles()]


@router.get("/summary", response_model=CompatibilitySummaryRead)
def compatibility_summary(
    device_id: str,
    db: DatabaseSession,
    library_id: str | None = None,
) -> CompatibilitySummaryRead:
    profile = _profile_or_404(device_id)
    query = _media_query().order_by(MediaFile.relative_path)
    if library_id:
        query = query.where(MediaFile.library_id == library_id)
    evaluations = [
        evaluate_file(media_file, profile)
        for media_file in db.scalars(query).unique().all()
    ]

    counts = {
        "direct_play": 0,
        "remux": 0,
        "audio_transcode": 0,
        "video_transcode": 0,
        "unsupported": 0,
        "unknown": 0,
    }
    issue_counts: dict[str, int] = {}
    for evaluation in evaluations:
        counts[evaluation.outcome] += 1
        for reason in evaluation.reasons:
            if reason.code == "compatible":
                continue
            issue_counts[reason.code] = issue_counts.get(reason.code, 0) + 1

    total = len(evaluations)
    direct_percent = round((counts["direct_play"] / total * 100), 1) if total else 0.0
    return CompatibilitySummaryRead(
        device=profile.read_model(),
        total_files=total,
        direct_play=counts["direct_play"],
        remux=counts["remux"],
        audio_transcode=counts["audio_transcode"],
        video_transcode=counts["video_transcode"],
        unsupported=counts["unsupported"],
        unknown=counts["unknown"],
        direct_play_percent=direct_percent,
        issue_counts=dict(
            sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
    )


@router.get("/files", response_model=CompatibilityFileListRead)
def compatibility_files(
    device_id: str,
    db: DatabaseSession,
    library_id: str | None = None,
    outcome: OutcomeFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CompatibilityFileListRead:
    profile = _profile_or_404(device_id)
    query = _media_query().order_by(MediaFile.relative_path)
    if library_id:
        query = query.where(MediaFile.library_id == library_id)
    evaluations = [
        evaluate_file(media_file, profile)
        for media_file in db.scalars(query).unique().all()
    ]
    if outcome:
        evaluations = [
            evaluation for evaluation in evaluations if evaluation.outcome == outcome
        ]
    return CompatibilityFileListRead(
        device=profile.read_model(),
        total_matching=len(evaluations),
        files=evaluations[offset : offset + limit],
    )


@router.get("/files/{file_id}", response_model=FileCompatibilityRead)
def file_compatibility(
    file_id: str,
    device_id: str,
    db: DatabaseSession,
) -> FileCompatibilityRead:
    profile = _profile_or_404(device_id)
    media_file = db.scalar(_media_query().where(MediaFile.id == file_id))
    if media_file is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEDIA_FILE_NOT_FOUND",
                "message": "The requested media file does not exist.",
                "details": {"file_id": file_id},
            },
        )
    return evaluate_file(media_file, profile)
