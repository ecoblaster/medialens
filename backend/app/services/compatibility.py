from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.media import AudioStream, MediaFile, SubtitleStream, VideoStream
from app.schemas.compatibility import (
    CompatibilityReasonRead,
    DeviceProfileRead,
    FileCompatibilityRead,
)


@dataclass(frozen=True)
class DeviceProfile:
    id: str
    name: str
    family: str
    description: str
    caveats: tuple[str, ...]
    containers: frozenset[str]
    video_codecs: frozenset[str]
    hdr_formats: frozenset[str]
    dolby_vision_profiles: frozenset[str]
    audio_codecs: frozenset[str]
    subtitle_codecs: frozenset[str]
    maximum_width: int = 3840
    maximum_height: int = 2160
    maximum_bit_depth: int = 10
    source_labels: tuple[str, ...] = ()

    def read_model(self) -> DeviceProfileRead:
        return DeviceProfileRead(
            id=self.id,
            name=self.name,
            family=self.family,
            description=self.description,
            caveats=list(self.caveats),
            supported_containers=sorted(self.containers),
            supported_video_codecs=sorted(self.video_codecs),
            supported_hdr_formats=sorted(self.hdr_formats),
            supported_dolby_vision_profiles=sorted(self.dolby_vision_profiles),
            supported_audio_codecs=sorted(self.audio_codecs),
            supported_subtitle_codecs=sorted(self.subtitle_codecs),
            maximum_width=self.maximum_width,
            maximum_height=self.maximum_height,
            maximum_bit_depth=self.maximum_bit_depth,
            source_labels=list(self.source_labels),
        )


COMMON_ANDROID_CONTAINERS = frozenset(
    {"mkv", "mp4", "mov", "m4v", "ts", "m2ts", "webm", "avi"}
)
COMMON_ANDROID_AUDIO = frozenset(
    {
        "aac",
        "ac3",
        "eac3",
        "truehd",
        "dts",
        "flac",
        "opus",
        "mp3",
        "vorbis",
        "pcm_s16le",
        "pcm_s24le",
    }
)
COMMON_ANDROID_SUBTITLES = frozenset(
    {
        "subrip",
        "srt",
        "ass",
        "ssa",
        "webvtt",
        "mov_text",
        "hdmv_pgs_subtitle",
        "pgs",
        "dvd_subtitle",
    }
)


DEVICE_PROFILES: dict[str, DeviceProfile] = {
    "nvidia-shield-tv-pro-2019": DeviceProfile(
        id="nvidia-shield-tv-pro-2019",
        name="NVIDIA Shield TV Pro (2019)",
        family="Android TV",
        description="High-end local playback profile with broad codec and passthrough support.",
        caveats=(
            "Results assume a capable playback app such as Plex, Jellyfin, Kodi, or Emby.",
            "Dolby Vision Profile 7 behavior can depend on the app, container, enhancement layer, and display chain.",
            "AV1 is treated as unsupported on the 2019 hardware.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "mpeg2video", "vp9", "vc1"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "7", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=("NVIDIA Shield TV specifications", "Playback-app behavior varies"),
    ),
    "apple-tv-4k-3rd-gen": DeviceProfile(
        id="apple-tv-4k-3rd-gen",
        name="Apple TV 4K (3rd gen)",
        family="tvOS",
        description="Apple TV profile emphasizing native tvOS decode formats and conservative lossless-audio handling.",
        caveats=(
            "Third-party apps may decode additional audio formats to multichannel PCM.",
            "Dolby TrueHD and DTS-family tracks are classified as audio transcode rather than native bitstream Direct Play.",
            "Dolby Vision Profile 7 is treated as unsupported; Profile 5 and compatible Profile 8 are accepted.",
        ),
        containers=frozenset({"mp4", "mov", "m4v", "mkv"}),
        video_codecs=frozenset({"h264", "hevc", "h265", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=frozenset({"aac", "ac3", "eac3", "alac", "flac", "mp3", "pcm_s16le", "pcm_s24le"}),
        subtitle_codecs=frozenset({"subrip", "srt", "webvtt", "mov_text", "ass", "ssa"}),
        source_labels=("Apple TV 4K technical specifications", "Third-party app behavior varies"),
    ),
    "fire-tv-cube-3rd-gen": DeviceProfile(
        id="fire-tv-cube-3rd-gen",
        name="Fire TV Cube (3rd gen)",
        family="Fire TV",
        description="Modern Fire TV profile with AV1, HDR10+, Dolby Vision, and broad Dolby audio support.",
        caveats=(
            "Playback behavior varies by application and Fire OS version.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported.",
            "Image subtitles may require app-specific rendering or video transcoding.",
        ),
        containers=frozenset({"mkv", "mp4", "mov", "m4v", "ts", "m2ts", "webm"}),
        video_codecs=frozenset({"h264", "hevc", "h265", "av1", "vp9", "mpeg2video"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=frozenset({"aac", "ac3", "eac3", "truehd", "flac", "opus", "mp3", "vorbis"}),
        subtitle_codecs=frozenset({"subrip", "srt", "webvtt", "mov_text", "ass", "ssa"}),
        source_labels=("Amazon Fire TV device specifications", "Playback-app behavior varies"),
    ),
    "ugoos-am6b-plus-coreelec": DeviceProfile(
        id="ugoos-am6b-plus-coreelec",
        name="Ugoos AM6B Plus (CoreELEC)",
        family="Ugoos / CoreELEC",
        description="Enthusiast local-playback profile for the S922X-J AM6B Plus running CoreELEC and Kodi.",
        caveats=(
            "This profile assumes CoreELEC and Kodi, not the stock Android playback stack.",
            "Dolby Vision Profile 7 and enhancement-layer behavior depend on the CoreELEC build, Kodi version, container, and HDMI chain.",
            "AV1 is unsupported by the S922X-J hardware.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "vp9", "mpeg2video", "vc1", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "7", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Ugoos AM6B Plus hardware specifications",
            "Ugoos AM6 firmware notes",
            "CoreELEC and Kodi playback configuration",
        ),
    ),
    "ugoos-sk1": DeviceProfile(
        id="ugoos-sk1",
        name="Ugoos SK1",
        family="Ugoos Android",
        description="Licensed S928X-K flagship profile with 8K decode, AV1, HDR10+, Dolby Vision, Dolby Audio, and DTS.",
        caveats=(
            "Results assume current Ugoos firmware and a capable local playback application.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; Profiles 5 and 8 are accepted.",
            "8K capability describes hardware decode limits; application and display-chain behavior can still vary.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "av1", "vp9", "mpeg2video", "vc1", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        maximum_width=7680,
        maximum_height=4320,
        source_labels=(
            "Ugoos SK1 official specifications",
            "Ugoos AM8 and SK1 firmware notes",
            "Playback-app behavior varies",
        ),
    ),
    "ugoos-am8-pro": DeviceProfile(
        id="ugoos-am8-pro",
        name="Ugoos AM8 Pro",
        family="Ugoos Android",
        description="High-end S928X-J local-playback profile with 8K AV1/HEVC/VP9 decode and current Ugoos Android firmware.",
        caveats=(
            "AM8 and AM8 Pro share the same playback SoC; the Pro model mainly adds memory and storage.",
            "Results assume current Ugoos firmware and a capable local playback application.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; Profiles 5 and 8 are accepted.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "av1", "vp9", "mpeg2video", "vc1", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        maximum_width=7680,
        maximum_height=4320,
        source_labels=(
            "Ugoos AM8 Pro official specifications",
            "Ugoos AM8 and SK1 firmware notes",
            "Playback-app behavior varies",
        ),
    ),
    "ugoos-am9-pro": DeviceProfile(
        id="ugoos-am9-pro",
        name="Ugoos AM9 Pro",
        family="Ugoos Android",
        description="Current S905X5-J profile with 4K120-class decode for VVC, AV1, VP9, and HEVC, with 4K60 HDMI output.",
        caveats=(
            "The official profile lists Widevine L3 and does not list Dolby Vision certification, so Dolby Vision is treated as unsupported.",
            "The SoC can decode several formats at up to 4K120, while the advertised HDMI output limit is 4K60.",
            "Lossless-audio passthrough remains application, firmware, receiver, and HDMI-chain dependent.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "av1", "vp9", "h266", "vvc", "mpeg2video", "vc1", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG"}),
        dolby_vision_profiles=frozenset(),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Ugoos AM9 Pro official specifications",
            "Ugoos AM9 Pro firmware notes",
            "Playback-app behavior varies",
        ),
    ),
    "ugoos-sk4-pro": DeviceProfile(
        id="ugoos-sk4-pro",
        name="Ugoos SK4 Pro",
        family="Ugoos Android",
        description="Compact licensed S905X5M-K profile with AV1, HEVC, VP9, Dolby Vision, Dolby Audio, and DTS at up to 4K60.",
        caveats=(
            "Results assume current Ugoos firmware and a capable local playback application.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; Profiles 5 and 8 are accepted.",
            "The device uses 100 Mbps Ethernet, which may be a practical bottleneck for very high-bitrate remuxes even when codecs are compatible.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "av1", "vp9", "mpeg2video", "vc1", "mpeg4"}),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Ugoos SK4 Pro official specifications",
            "Ugoos SK4 firmware notes",
            "Playback-app behavior varies",
        ),
    ),
}


def list_device_profiles() -> list[DeviceProfile]:
    return list(DEVICE_PROFILES.values())


def get_device_profile(device_id: str) -> DeviceProfile | None:
    return DEVICE_PROFILES.get(device_id)


def _normalize_container(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "matroska" in lowered:
        return "mkv"
    if "webm" in lowered:
        return "webm"
    if any(token in lowered for token in ("mov", "mp4", "m4a", "3gp", "mj2")):
        return "mp4"
    if "mpegts" in lowered or lowered in {"ts", "m2ts"}:
        return "m2ts" if lowered == "m2ts" else "ts"
    return lowered.split(",", 1)[0].strip().lstrip(".")


def _default_stream[T](streams: Iterable[T]) -> T | None:
    values = list(streams)
    if not values:
        return None
    return next(
        (stream for stream in values if bool(getattr(stream, "is_default", False))),
        values[0],
    )


def _hdr_format(video: VideoStream | None) -> tuple[str | None, str | None]:
    if video is None:
        return None, None
    if video.has_dolby_vision:
        profile = video.dolby_vision.profile if video.dolby_vision else None
        return "DOLBY_VISION", profile
    if video.has_hdr10_plus:
        return "HDR10_PLUS", None
    return video.base_hdr_format or None, None


def _reason(
    component: str,
    code: str,
    message: str,
    severity: str = "warning",
) -> CompatibilityReasonRead:
    return CompatibilityReasonRead(
        component=component,
        code=code,
        message=message,
        severity=severity,
    )


def evaluate_file(media_file: MediaFile, profile: DeviceProfile) -> FileCompatibilityRead:
    video = _default_stream(media_file.video_streams)
    audio = _default_stream(media_file.audio_streams)
    subtitle = _default_stream(
        stream
        for stream in media_file.subtitle_streams
        if stream.is_forced or stream.is_default
    )
    container = _normalize_container(media_file.container)
    hdr_format, dv_profile = _hdr_format(video)
    reasons: list[CompatibilityReasonRead] = []
    outcome = "direct_play"

    if media_file.scan_status != "complete":
        outcome = "unknown"
        reasons.append(
            _reason(
                "metadata",
                "file_not_fully_scanned",
                "The file has not completed a successful metadata scan.",
            )
        )

    if video is None:
        outcome = "unsupported"
        reasons.append(
            _reason(
                "video",
                "missing_video_stream",
                "No video stream was detected.",
                "error",
            )
        )
    else:
        codec = video.codec_name.lower()
        if codec not in profile.video_codecs:
            outcome = "video_transcode"
            reasons.append(
                _reason(
                    "video",
                    "unsupported_video_codec",
                    f"{profile.name} does not list {codec.upper()} as a supported video codec.",
                )
            )
        if (
            video.width
            and video.width > profile.maximum_width
            or video.height
            and video.height > profile.maximum_height
        ):
            outcome = "video_transcode"
            reasons.append(
                _reason(
                    "video",
                    "resolution_exceeds_profile",
                    f"Resolution {video.width or '?'}×{video.height or '?'} exceeds the profile limit.",
                )
            )
        if video.bit_depth and video.bit_depth > profile.maximum_bit_depth:
            outcome = "video_transcode"
            reasons.append(
                _reason(
                    "video",
                    "bit_depth_exceeds_profile",
                    f"{video.bit_depth}-bit video exceeds the {profile.maximum_bit_depth}-bit profile limit.",
                )
            )

        if hdr_format in {None, "UNKNOWN"}:
            if outcome == "direct_play":
                outcome = "unknown"
            reasons.append(
                _reason(
                    "metadata",
                    "unknown_hdr_metadata",
                    "HDR compatibility cannot be confirmed because the stream metadata is incomplete.",
                )
            )
        elif hdr_format not in profile.hdr_formats:
            outcome = "video_transcode"
            reasons.append(
                _reason(
                    "hdr",
                    "unsupported_hdr_format",
                    f"{profile.name} does not support {hdr_format.replace('_', ' ')} in this profile.",
                )
            )
        elif hdr_format == "DOLBY_VISION":
            if not dv_profile:
                if outcome == "direct_play":
                    outcome = "unknown"
                reasons.append(
                    _reason(
                        "metadata",
                        "unknown_dolby_vision_profile",
                        "Dolby Vision was detected but its profile is unknown.",
                    )
                )
            elif dv_profile not in profile.dolby_vision_profiles:
                outcome = "video_transcode"
                reasons.append(
                    _reason(
                        "hdr",
                        "unsupported_dolby_vision_profile",
                        f"Dolby Vision Profile {dv_profile} is not supported by this device profile.",
                    )
                )

    if audio is not None:
        codec = audio.codec_name.lower()
        if codec not in profile.audio_codecs and outcome not in {
            "unsupported",
            "video_transcode",
        }:
            outcome = "audio_transcode"
            reasons.append(
                _reason(
                    "audio",
                    "unsupported_audio_codec",
                    f"The selected {codec.upper()} audio track requires decoding or transcoding.",
                )
            )
    else:
        reasons.append(
            _reason(
                "audio",
                "missing_audio_stream",
                "No audio stream was detected.",
                "info",
            )
        )

    if container is None:
        if outcome == "direct_play":
            outcome = "unknown"
        reasons.append(
            _reason(
                "metadata",
                "unknown_container",
                "The container format is unknown.",
            )
        )
    elif container not in profile.containers and outcome == "direct_play":
        outcome = "remux"
        reasons.append(
            _reason(
                "container",
                "container_requires_remux",
                f"The {container.upper()} container is not in this device profile, but the selected streams may be remuxed without video conversion.",
            )
        )

    if subtitle is not None:
        codec = subtitle.codec_name.lower()
        if codec not in profile.subtitle_codecs:
            if outcome in {"direct_play", "remux", "audio_transcode"}:
                outcome = "video_transcode"
            reasons.append(
                _reason(
                    "subtitle",
                    "subtitle_requires_burn_in",
                    f"The selected {codec.upper()} subtitle track may require burn-in, causing video transcoding.",
                )
            )

    if not reasons:
        reasons.append(
            _reason(
                "metadata",
                "compatible",
                "The selected streams match this device profile.",
                "info",
            )
        )

    return FileCompatibilityRead(
        file_id=media_file.id,
        library_id=media_file.library_id,
        relative_path=media_file.relative_path,
        title=media_file.media_item.title,
        year=media_file.media_item.year,
        outcome=outcome,
        selected_container=container,
        selected_video_codec=video.codec_name if video else None,
        selected_hdr_format=hdr_format,
        selected_dolby_vision_profile=dv_profile,
        selected_audio_codec=audio.codec_name if audio else None,
        selected_subtitle_codec=subtitle.codec_name if subtitle else None,
        reasons=reasons,
    )
