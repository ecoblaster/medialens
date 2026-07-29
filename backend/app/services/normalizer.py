from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.models.enums import BaseHdrFormat, DolbyVisionEnhancementLayer, ImmersiveFormat, SubtitleFormatClass


@dataclass(frozen=True)
class DolbyVisionData:
    profile: str
    level: int | None
    compatibility_id: int | None
    bl_present: bool
    el_present: bool
    rpu_present: bool
    el_type: str
    detected_by: str


@dataclass(frozen=True)
class VideoData:
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
    dolby_vision: DolbyVisionData | None = None


@dataclass(frozen=True)
class AudioData:
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


@dataclass(frozen=True)
class SubtitleData:
    stream_index: int
    codec_name: str
    format_class: str
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    is_hearing_impaired: bool


@dataclass(frozen=True)
class NormalizedMedia:
    container: str | None
    duration_ms: int | None
    overall_bitrate: int | None
    videos: list[VideoData] = field(default_factory=list)
    audios: list[AudioData] = field(default_factory=list)
    subtitles: list[SubtitleData] = field(default_factory=list)


def _as_int(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _duration_ms(value: Any) -> int | None:
    try:
        return round(float(str(value)) * 1000)
    except (TypeError, ValueError):
        return None


def _fraction(value: Any) -> tuple[int | None, int | None]:
    if not value or value in {"0/0", "N/A"}:
        return None, None
    try:
        rate = Fraction(str(value))
        return rate.numerator, rate.denominator
    except (ValueError, ZeroDivisionError):
        return None, None


def _dict(stream: dict[str, Any], key: str) -> dict[str, Any]:
    value = stream.get(key)
    return value if isinstance(value, dict) else {}


def _side_data(stream: dict[str, Any]) -> list[dict[str, Any]]:
    value = stream.get("side_data_list")
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _bit_depth(stream: dict[str, Any]) -> int | None:
    direct = _as_int(stream.get("bits_per_raw_sample")) or _as_int(stream.get("bits_per_sample"))
    if direct:
        return direct
    match = re.search(r"p(\d{2})(?:le|be)?$", str(stream.get("pix_fmt") or ""))
    return int(match.group(1)) if match else None


def _base_hdr(stream: dict[str, Any]) -> str:
    transfer = str(stream.get("color_transfer") or "").lower()
    if transfer in {"smpte2084", "pq"}:
        return BaseHdrFormat.HDR10.value
    if transfer in {"arib-std-b67", "hlg"}:
        return BaseHdrFormat.HLG.value
    return BaseHdrFormat.SDR.value if transfer else BaseHdrFormat.UNKNOWN.value


def _dv(stream: dict[str, Any]) -> DolbyVisionData | None:
    for item in _side_data(stream):
        side_type = str(item.get("side_data_type") or "").lower()
        if "dovi" not in side_type and "dolby vision" not in side_type:
            continue
        profile = _as_int(item.get("dv_profile"))
        el_present = bool(_as_int(item.get("el_present_flag")) or 0)
        return DolbyVisionData(
            profile=str(profile) if profile is not None else "unknown",
            level=_as_int(item.get("dv_level")),
            compatibility_id=_as_int(item.get("dv_bl_signal_compatibility_id")),
            bl_present=bool(_as_int(item.get("bl_present_flag")) or 0),
            el_present=el_present,
            rpu_present=bool(_as_int(item.get("rpu_present_flag")) or 0),
            el_type=DolbyVisionEnhancementLayer.UNKNOWN.value if el_present else DolbyVisionEnhancementLayer.NONE.value,
            detected_by="ffprobe",
        )
    return None


def _contains_hdr10_plus(value: Any) -> bool:
    text = str(value or "").lower()
    return any(
        token in text
        for token in (
            "hdr10+",
            "hdr10 plus",
            "smpte st 2094-40",
            "smpte2094-40",
            "st 2094 app 4",
            "dynamic hdr plus",
            "dynamic hdr10+",
        )
    )


def _recursive_contains_hdr10_plus(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_hdr10_plus(key) or _recursive_contains_hdr10_plus(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_recursive_contains_hdr10_plus(item) for item in value)
    return _contains_hdr10_plus(value)


def _mediainfo_video_tracks(mediainfo: dict[str, Any]) -> list[dict[str, Any]]:
    media = mediainfo.get("media")
    if not isinstance(media, dict):
        return []
    tracks = media.get("track")
    if not isinstance(tracks, list):
        return []
    return [track for track in tracks if isinstance(track, dict) and str(track.get("@type") or "").lower() == "video"]


def _mediainfo_has_hdr10_plus(mediainfo: dict[str, Any], video_ordinal: int) -> bool:
    summary = mediainfo.get("medialens_hdr_summary")
    if _contains_hdr10_plus(summary):
        return True
    tracks = _mediainfo_video_tracks(mediainfo)
    if video_ordinal < len(tracks) and _recursive_contains_hdr10_plus(tracks[video_ordinal]):
        return True
    return _recursive_contains_hdr10_plus(mediainfo)


def _ffprobe_probe_items_have_hdr10_plus(ffprobe: dict[str, Any], stream_index: int) -> bool:
    probe = ffprobe.get("medialens_hdr10_plus_probe")
    if not isinstance(probe, dict):
        return False
    for collection_name in ("packets", "frames"):
        items = probe.get(collection_name)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_stream_index = _as_int(item.get("stream_index"))
            if item_stream_index is not None and item_stream_index != stream_index:
                continue
            if _recursive_contains_hdr10_plus(item):
                return True
    return False


def _stream_has_hdr10_plus(stream: dict[str, Any]) -> bool:
    return _recursive_contains_hdr10_plus(_side_data(stream))


def _immersive(stream: dict[str, Any]) -> str:
    tags = _dict(stream, "tags")
    text = " ".join(str(x or "") for x in (stream.get("codec_name"), stream.get("profile"), tags.get("title"))).lower()
    if "dts:x" in text or "dts x" in text:
        return ImmersiveFormat.DTS_X.value
    if "atmos" in text or "joc" in text:
        return ImmersiveFormat.DOLBY_ATMOS.value
    if "auro" in text:
        return ImmersiveFormat.AURO_3D.value
    return ImmersiveFormat.NONE.value


def _subtitle_class(codec: str) -> str:
    if codec in {"dvd_subtitle", "dvb_subtitle", "hdmv_pgs_subtitle", "xsub"}:
        return SubtitleFormatClass.IMAGE.value
    if codec in {"ass", "ssa", "subrip", "srt", "mov_text", "webvtt", "text"}:
        return SubtitleFormatClass.TEXT.value
    return SubtitleFormatClass.UNKNOWN.value


def normalize_probe(ffprobe: dict[str, Any], mediainfo: dict[str, Any], path: Path) -> NormalizedMedia:
    del path
    format_data = ffprobe.get("format") if isinstance(ffprobe.get("format"), dict) else {}
    streams = ffprobe.get("streams") if isinstance(ffprobe.get("streams"), list) else []
    videos: list[VideoData] = []
    audios: list[AudioData] = []
    subtitles: list[SubtitleData] = []
    video_ordinal = 0
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = str(stream.get("codec_type") or "")
        codec = str(stream.get("codec_name") or "unknown")
        tags = _dict(stream, "tags")
        disposition = _dict(stream, "disposition")
        index = _as_int(stream.get("index")) or 0
        if codec_type == "video":
            num, den = _fraction(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            dv = _dv(stream)
            has_hdr10_plus = (
                _stream_has_hdr10_plus(stream)
                or _ffprobe_probe_items_have_hdr10_plus(ffprobe, index)
                or _mediainfo_has_hdr10_plus(mediainfo, video_ordinal)
            )
            videos.append(
                VideoData(
                    index,
                    codec,
                    stream.get("profile"),
                    _as_int(stream.get("width")),
                    _as_int(stream.get("height")),
                    stream.get("pix_fmt"),
                    _bit_depth(stream),
                    _as_int(stream.get("bit_rate")),
                    num,
                    den,
                    stream.get("color_primaries"),
                    stream.get("color_transfer"),
                    stream.get("color_space"),
                    _base_hdr(stream),
                    has_hdr10_plus,
                    dv is not None,
                    tags.get("language"),
                    tags.get("title"),
                    bool(disposition.get("default", 0)),
                    bool(disposition.get("forced", 0)),
                    dv,
                )
            )
            video_ordinal += 1
        elif codec_type == "audio":
            title = tags.get("title")
            audios.append(
                AudioData(
                    index,
                    codec,
                    stream.get("profile"),
                    _as_int(stream.get("channels")),
                    stream.get("channel_layout"),
                    _as_int(stream.get("sample_rate")),
                    _as_int(stream.get("bits_per_raw_sample")) or _as_int(stream.get("bits_per_sample")),
                    _as_int(stream.get("bit_rate")),
                    _immersive(stream),
                    tags.get("language"),
                    title,
                    bool(disposition.get("default", 0)),
                    bool(disposition.get("forced", 0)),
                    "commentary" in str(title or "").lower(),
                )
            )
        elif codec_type == "subtitle":
            title = tags.get("title")
            subtitles.append(
                SubtitleData(
                    index,
                    codec,
                    _subtitle_class(codec),
                    tags.get("language"),
                    title,
                    bool(disposition.get("default", 0)),
                    bool(disposition.get("forced", 0)),
                    bool(disposition.get("hearing_impaired", 0)) or "sdh" in str(title or "").lower(),
                )
            )
    format_name = str(format_data.get("format_name") or "")
    return NormalizedMedia(
        format_name.split(",")[0] or None,
        _duration_ms(format_data.get("duration")),
        _as_int(format_data.get("bit_rate")),
        videos,
        audios,
        subtitles,
    )
