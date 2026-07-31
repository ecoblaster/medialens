from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DolbyVisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    profile: str
    level: int | None
    compatibility_id: int | None
    bl_present: bool
    el_present: bool
    rpu_present: bool
    el_type: str
    detected_by: str


class VideoStreamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stream_index: int
    codec_name: str
    codec_profile: str | None
    width: int | None
    height: int | None
    pixel_format: str | None
    bit_depth: int | None
    bitrate: int | None
    frame_rate_num: int | None
    frame_rate_den: int | None
    color_primaries: str | None
    color_transfer: str | None
    color_matrix: str | None
    base_hdr_format: str
    has_hdr10_plus: bool
    has_dolby_vision: bool
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    dolby_vision: DolbyVisionRead | None


class AudioStreamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stream_index: int
    codec_name: str
    codec_profile: str | None
    channels: int | None
    channel_layout: str | None
    sample_rate: int | None
    bit_depth: int | None
    bitrate: int | None
    immersive_format: str
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    is_commentary: bool


class SubtitleStreamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stream_index: int
    codec_name: str
    format_class: str
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    is_hearing_impaired: bool


class MediaItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    item_type: str
    title: str
    year: int | None


class MediaFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    library_id: str
    relative_path: str
    filename: str
    version_label: str | None
    part_index: int
    is_primary: bool
    container: str | None
    size_bytes: int
    duration_ms: int | None
    overall_bitrate: int | None
    scan_status: str
    last_error: str | None
    last_scanned_at: datetime | None
    media_item: MediaItemSummary
    video_streams: list[VideoStreamRead]
    audio_streams: list[AudioStreamRead]
    subtitle_streams: list[SubtitleStreamRead]
