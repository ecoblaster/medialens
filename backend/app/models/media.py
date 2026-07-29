from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now
from app.models.enums import (
    BaseHdrFormat,
    DolbyVisionEnhancementLayer,
    FileScanStatus,
    ImmersiveFormat,
    ItemType,
    SubtitleFormatClass,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.library import Library
    from app.models.scan import ScanFileResult, ScanRun


class MediaItem(TimestampMixin, Base):
    __tablename__ = "media_items"
    __table_args__ = (
        Index("ix_media_items_library_type", "library_id", "item_type"),
        Index("ix_media_items_parent_id", "parent_id"),
        Index("ix_media_items_title", "title"),
        UniqueConstraint(
            "library_id", "external_source", "external_id", name="external_identity"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE")
    )
    item_type: Mapped[str] = mapped_column(
        String(20), default=ItemType.UNKNOWN.value, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_title: Mapped[str | None] = mapped_column(String(512))
    year: Mapped[int | None] = mapped_column(Integer)
    season_number: Mapped[int | None] = mapped_column(Integer)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    external_source: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_guid: Mapped[str | None] = mapped_column(String(1024))
    poster_key: Mapped[str | None] = mapped_column(String(2048))

    library: Mapped["Library"] = relationship(back_populates="media_items")
    parent: Mapped["MediaItem | None"] = relationship(
        remote_side="MediaItem.id", back_populates="children"
    )
    children: Mapped[list["MediaItem"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    files: Mapped[list["MediaFile"]] = relationship(
        back_populates="media_item", cascade="all, delete-orphan"
    )


class MediaFile(TimestampMixin, Base):
    __tablename__ = "media_files"
    __table_args__ = (
        UniqueConstraint("library_id", "relative_path", name="library_relative_path"),
        Index("ix_media_files_media_item_id", "media_item_id"),
        Index("ix_media_files_scan_status", "scan_status"),
        Index("ix_media_files_mtime_ns", "mtime_ns"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_item_id: Mapped[str] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(String(4096), nullable=False)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(255))
    part_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    container: Mapped[str | None] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    overall_bitrate: Mapped[int | None] = mapped_column(BigInteger)
    mtime_ns: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    quick_hash: Mapped[str | None] = mapped_column(String(255))
    scan_status: Mapped[str] = mapped_column(
        String(20), default=FileScanStatus.PENDING.value, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    media_item: Mapped[MediaItem] = relationship(back_populates="files")
    library: Mapped["Library"] = relationship(back_populates="media_files")
    video_streams: Mapped[list["VideoStream"]] = relationship(
        back_populates="media_file", cascade="all, delete-orphan"
    )
    audio_streams: Mapped[list["AudioStream"]] = relationship(
        back_populates="media_file", cascade="all, delete-orphan"
    )
    subtitle_streams: Mapped[list["SubtitleStream"]] = relationship(
        back_populates="media_file", cascade="all, delete-orphan"
    )
    probe_snapshots: Mapped[list["ProbeSnapshot"]] = relationship(
        back_populates="media_file", cascade="all, delete-orphan"
    )
    scan_results: Mapped[list["ScanFileResult"]] = relationship(
        back_populates="media_file"
    )


class VideoStream(Base):
    __tablename__ = "video_streams"
    __table_args__ = (
        UniqueConstraint("media_file_id", "stream_index", name="file_stream_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_file_id: Mapped[str] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    stream_index: Mapped[int] = mapped_column(Integer, nullable=False)
    codec_name: Mapped[str] = mapped_column(String(100), nullable=False)
    codec_profile: Mapped[str | None] = mapped_column(String(255))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    pixel_format: Mapped[str | None] = mapped_column(String(100))
    bit_depth: Mapped[int | None] = mapped_column(Integer)
    bitrate: Mapped[int | None] = mapped_column(BigInteger)
    frame_rate_num: Mapped[int | None] = mapped_column(Integer)
    frame_rate_den: Mapped[int | None] = mapped_column(Integer)
    color_primaries: Mapped[str | None] = mapped_column(String(100))
    color_transfer: Mapped[str | None] = mapped_column(String(100))
    color_matrix: Mapped[str | None] = mapped_column(String(100))
    base_hdr_format: Mapped[str] = mapped_column(
        String(20), default=BaseHdrFormat.UNKNOWN.value, nullable=False
    )
    has_hdr10_plus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_dolby_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(512))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_forced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    media_file: Mapped[MediaFile] = relationship(back_populates="video_streams")
    dolby_vision: Mapped["DolbyVisionMetadata | None"] = relationship(
        back_populates="video_stream", cascade="all, delete-orphan", uselist=False
    )


class DolbyVisionMetadata(TimestampMixin, Base):
    __tablename__ = "dolby_vision_metadata"
    __table_args__ = (UniqueConstraint("video_stream_id", name="video_stream"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_stream_id: Mapped[str] = mapped_column(
        ForeignKey("video_streams.id", ondelete="CASCADE"), nullable=False
    )
    profile: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[int | None] = mapped_column(Integer)
    compatibility_id: Mapped[int | None] = mapped_column(Integer)
    bl_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    el_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rpu_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    el_type: Mapped[str] = mapped_column(
        String(20), default=DolbyVisionEnhancementLayer.UNKNOWN.value, nullable=False
    )
    detected_by: Mapped[str] = mapped_column(String(100), nullable=False)

    video_stream: Mapped[VideoStream] = relationship(back_populates="dolby_vision")


class AudioStream(Base):
    __tablename__ = "audio_streams"
    __table_args__ = (
        UniqueConstraint("media_file_id", "stream_index", name="file_stream_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_file_id: Mapped[str] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    stream_index: Mapped[int] = mapped_column(Integer, nullable=False)
    codec_name: Mapped[str] = mapped_column(String(100), nullable=False)
    codec_profile: Mapped[str | None] = mapped_column(String(255))
    channels: Mapped[int | None] = mapped_column(Integer)
    channel_layout: Mapped[str | None] = mapped_column(String(100))
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    bit_depth: Mapped[int | None] = mapped_column(Integer)
    bitrate: Mapped[int | None] = mapped_column(BigInteger)
    immersive_format: Mapped[str] = mapped_column(
        String(30), default=ImmersiveFormat.NONE.value, nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(512))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_forced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_commentary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    media_file: Mapped[MediaFile] = relationship(back_populates="audio_streams")


class SubtitleStream(Base):
    __tablename__ = "subtitle_streams"
    __table_args__ = (
        UniqueConstraint("media_file_id", "stream_index", name="file_stream_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_file_id: Mapped[str] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    stream_index: Mapped[int] = mapped_column(Integer, nullable=False)
    codec_name: Mapped[str] = mapped_column(String(100), nullable=False)
    format_class: Mapped[str] = mapped_column(
        String(20), default=SubtitleFormatClass.UNKNOWN.value, nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(512))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_forced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hearing_impaired: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    media_file: Mapped[MediaFile] = relationship(back_populates="subtitle_streams")


class ProbeSnapshot(Base):
    __tablename__ = "probe_snapshots"
    __table_args__ = (Index("ix_probe_snapshots_file_tool", "media_file_id", "tool_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_file_id: Mapped[str] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    scan_run_id: Mapped[str] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[str | None] = mapped_column(String(100))
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    media_file: Mapped[MediaFile] = relationship(back_populates="probe_snapshots")
    scan_run: Mapped["ScanRun"] = relationship(back_populates="probe_snapshots")
