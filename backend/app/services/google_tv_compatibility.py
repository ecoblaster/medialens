from __future__ import annotations

from app.services.compatibility import (
    COMMON_ANDROID_CONTAINERS,
    DeviceProfile,
)


GOOGLE_TV_AUDIO = frozenset(
    {
        "aac",
        "ac3",
        "eac3",
        "flac",
        "opus",
        "mp3",
        "vorbis",
        "pcm_s16le",
        "pcm_s24le",
    }
)

GOOGLE_TV_SUBTITLES = frozenset(
    {
        "subrip",
        "srt",
        "ass",
        "ssa",
        "webvtt",
        "mov_text",
    }
)


GOOGLE_TV_DEVICE_PROFILES: dict[str, DeviceProfile] = {
    "google-tv-streamer-4k": DeviceProfile(
        id="google-tv-streamer-4k",
        name="Google TV Streamer (4K)",
        family="Google TV",
        description=(
            "Google's current 4K60 streaming box with AV1, HEVC, VP9, HDR10+, "
            "Dolby Vision, Dolby Atmos, and built-in Gigabit Ethernet."
        ),
        caveats=(
            "Results assume current Google TV firmware and a capable playback app such as Plex, Jellyfin, Kodi, or Emby.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; Profiles 5 and compatible Profile 8 are accepted.",
            "Google documents Dolby Atmos support without passthrough, so Dolby TrueHD and DTS-family tracks are classified as requiring audio conversion.",
            "Image-based subtitles may require app-specific rendering or video transcoding.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "vp9", "av1"}),
        hdr_formats=frozenset(
            {"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}
        ),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=GOOGLE_TV_AUDIO,
        subtitle_codecs=GOOGLE_TV_SUBTITLES,
        source_labels=(
            "Google TV Streamer official specifications",
            "Google Cast supported media documentation",
            "Playback-app behavior varies",
        ),
    ),
    "chromecast-with-google-tv-4k": DeviceProfile(
        id="chromecast-with-google-tv-4k",
        name="Chromecast with Google TV (4K)",
        family="Google TV",
        description=(
            "Google TV dongle profile with 4K60 HEVC and VP9 playback, HDR10+, "
            "Dolby Vision, and Dolby Atmos via HDMI passthrough."
        ),
        caveats=(
            "This profile represents the 4K model, not Chromecast with Google TV (HD).",
            "Results assume current Google TV firmware and a capable playback app such as Plex, Jellyfin, Kodi, or Emby.",
            "AV1 hardware decoding is not listed for the 4K Chromecast and is treated as unsupported.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; Profiles 5 and compatible Profile 8 are accepted.",
            "Official passthrough support is limited to Dolby formats; Dolby TrueHD and DTS-family tracks are classified as requiring audio conversion.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset({"h264", "hevc", "h265", "vp9"}),
        hdr_formats=frozenset(
            {"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}
        ),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=GOOGLE_TV_AUDIO,
        subtitle_codecs=GOOGLE_TV_SUBTITLES,
        source_labels=(
            "Chromecast with Google TV official specifications",
            "Google Cast supported media documentation",
            "Playback-app behavior varies",
        ),
    ),
}


def list_google_tv_device_profiles() -> list[DeviceProfile]:
    return list(GOOGLE_TV_DEVICE_PROFILES.values())


def get_google_tv_device_profile(device_id: str) -> DeviceProfile | None:
    return GOOGLE_TV_DEVICE_PROFILES.get(device_id)
