from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library import Library
from app.models.media import MediaFile, MediaItem, VideoStream
from app.services.media_versions import normalize_title_identity


def _video(width: int, height: int, *, hdr: str = "SDR") -> VideoStream:
    return VideoStream(
        stream_index=0,
        codec_name="hevc" if width >= 3000 else "h264",
        width=width,
        height=height,
        bitrate=50_000_000 if width >= 3000 else 12_000_000,
        base_hdr_format=hdr,
        has_hdr10_plus=False,
        has_dolby_vision=False,
    )


def test_normalize_title_identity_removes_quality_suffixes() -> None:
    assert normalize_title_identity("Casino Royale 2160p UHD BluRay Remux") == "casino royale"
    assert normalize_title_identity("Casino.Royale.1080p") == "casino royale"


def test_files_for_same_movie_are_grouped_as_versions(db_session: Session) -> None:
    library = Library(
        name="Movies",
        media_kind="movies",
        source_type="filesystem",
        root_path="/media/movies",
    )
    hd_item = MediaItem(
        library=library,
        item_type="movie",
        title="Casino Royale 1080p",
        year=2006,
    )
    uhd_item = MediaItem(
        library=library,
        item_type="movie",
        title="Casino Royale 2160p UHD BluRay Remux",
        year=2006,
    )
    hd_file = MediaFile(
        library=library,
        media_item=hd_item,
        relative_path="Casino Royale (2006)/Casino Royale 1080p.mkv",
        filename="Casino Royale 1080p.mkv",
        size_bytes=25_000_000_000,
        overall_bitrate=15_000_000,
        scan_status="complete",
        video_streams=[_video(1920, 1080)],
    )
    uhd_file = MediaFile(
        library=library,
        media_item=uhd_item,
        relative_path="Casino Royale (2006)/Casino Royale 2160p.mkv",
        filename="Casino Royale 2160p.mkv",
        size_bytes=70_000_000_000,
        overall_bitrate=55_000_000,
        scan_status="complete",
        video_streams=[_video(3840, 2160, hdr="HDR10")],
    )
    db_session.add_all([library, hd_file, uhd_file])
    db_session.commit()

    items = list(db_session.scalars(select(MediaItem)).all())
    files = list(db_session.scalars(select(MediaFile)).all())

    assert len(items) == 1
    assert {media_file.media_item_id for media_file in files} == {items[0].id}
    assert {media_file.version_label for media_file in files} == {
        "1080p · SDR",
        "4K · HDR10",
    }
    assert next(media_file for media_file in files if media_file.is_primary).id == uhd_file.id
