from __future__ import annotations

from app.services.compatibility import (
    COMMON_ANDROID_CONTAINERS,
    COMMON_ANDROID_SUBTITLES,
    DeviceProfile,
)

XIAOMI_DEVICE_PROFILES: dict[str, DeviceProfile] = {
    "xiaomi-tv-box-s-3rd-gen": DeviceProfile(
        id="xiaomi-tv-box-s-3rd-gen",
        name="Xiaomi TV Box S (3rd Gen)",
        family="Xiaomi Google TV",
        description=(
            "Compact Google TV profile with 4K60 AV1/HEVC/VP9 playback, "
            "HDR10+, Dolby Vision, Dolby Audio, and DTS:X."
        ),
        caveats=(
            "Results assume current Google TV firmware and a capable playback app "
            "such as Plex, Jellyfin, Kodi, or Emby.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported; "
            "Profiles 5 and compatible Profile 8 are accepted.",
            "Dolby TrueHD is classified as requiring audio conversion because "
            "Xiaomi does not document lossless Dolby passthrough.",
            "The device has no built-in Ethernet port; high-bitrate remux playback "
            "depends on Wi-Fi conditions or a compatible USB adapter.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset(
            {
                "h264",
                "hevc",
                "h265",
                "av1",
                "vp9",
                "mpeg1video",
                "mpeg2video",
                "mpeg4",
            }
        ),
        hdr_formats=frozenset({"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=frozenset(
            {
                "aac",
                "ac3",
                "eac3",
                "dts",
                "flac",
                "opus",
                "mp3",
                "vorbis",
                "pcm_s16le",
                "pcm_s24le",
            }
        ),
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Xiaomi TV Box S (3rd Gen) official specifications",
            "Xiaomi TV Box S (3rd Gen) official FAQ",
            "S905X5M platform decoder specifications",
            "Playback-app behavior varies",
        ),
    ),
}


def list_xiaomi_device_profiles() -> list[DeviceProfile]:
    return list(XIAOMI_DEVICE_PROFILES.values())


def get_xiaomi_device_profile(device_id: str) -> DeviceProfile | None:
    return XIAOMI_DEVICE_PROFILES.get(device_id)
