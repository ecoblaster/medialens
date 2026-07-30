from __future__ import annotations

from app.services.compatibility import (
    COMMON_ANDROID_AUDIO,
    COMMON_ANDROID_CONTAINERS,
    COMMON_ANDROID_SUBTITLES,
    DeviceProfile,
)


HOMATICS_DEVICE_PROFILES: dict[str, DeviceProfile] = {
    "homatics-box-r-4k-plus": DeviceProfile(
        id="homatics-box-r-4k-plus",
        name="Homatics Box R 4K Plus (Android TV)",
        family="Homatics Android TV",
        description=(
            "Certified S905X4-K streaming and local-playback profile with 4K60 AV1, "
            "HDR10+, Dolby Vision, Dolby Atmos, DTS, Widevine L1, and Gigabit Ethernet."
        ),
        caveats=(
            "This profile models the stock Android TV firmware; CoreELEC behavior is available as a separate profile.",
            "Results assume current firmware and a capable playback app such as Plex, Jellyfin, Kodi, or Emby.",
            "Dolby Vision Profile 7 is treated conservatively as unsupported on stock Android; Profiles 5 and compatible Profile 8 are accepted.",
            "Lossless-audio passthrough can vary by firmware, playback app, receiver, and HDMI chain.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset(
            {"h264", "hevc", "h265", "av1", "vp9", "mpeg2video", "vc1", "mpeg4"}
        ),
        hdr_formats=frozenset(
            {"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}
        ),
        dolby_vision_profiles=frozenset({"5", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Homatics Box R 4K Plus official specifications",
            "Homatics Android TV playback behavior",
            "Playback-app behavior varies",
        ),
    ),
    "homatics-box-r-4k-plus-coreelec": DeviceProfile(
        id="homatics-box-r-4k-plus-coreelec",
        name="Homatics Box R 4K Plus (CoreELEC)",
        family="Homatics / CoreELEC",
        description=(
            "Enthusiast S905X4-K profile for CoreELEC and Kodi with 4K60 AV1, "
            "Dolby Vision Profile 7/FEL-capable playback, and lossless-audio passthrough."
        ),
        caveats=(
            "This profile assumes CoreELEC and Kodi, not the stock Android TV playback stack.",
            "Dolby Vision Profile 7 and enhancement-layer behavior depend on compatible Android firmware, the CoreELEC build, Kodi version, container, and HDMI chain.",
            "Dolby TrueHD and DTS-HD passthrough require a compatible receiver and HDMI configuration.",
            "Certified Android streaming and DRM applications require booting the stock Android TV system.",
        ),
        containers=COMMON_ANDROID_CONTAINERS,
        video_codecs=frozenset(
            {"h264", "hevc", "h265", "av1", "vp9", "mpeg2video", "vc1", "mpeg4"}
        ),
        hdr_formats=frozenset(
            {"SDR", "HDR10", "HDR10_PLUS", "HLG", "DOLBY_VISION"}
        ),
        dolby_vision_profiles=frozenset({"5", "7", "8"}),
        audio_codecs=COMMON_ANDROID_AUDIO,
        subtitle_codecs=COMMON_ANDROID_SUBTITLES,
        source_labels=(
            "Homatics Box R 4K Plus official specifications",
            "CoreELEC Homatics installation guide",
            "CoreELEC Dolby Vision and lossless-audio support",
        ),
    ),
}


def list_homatics_device_profiles() -> list[DeviceProfile]:
    return list(HOMATICS_DEVICE_PROFILES.values())


def get_homatics_device_profile(device_id: str) -> DeviceProfile | None:
    return HOMATICS_DEVICE_PROFILES.get(device_id)
