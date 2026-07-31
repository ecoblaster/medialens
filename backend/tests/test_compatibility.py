from types import SimpleNamespace

from app.services.compatibility import evaluate_file, get_device_profile
from app.services.google_tv_compatibility import get_google_tv_device_profile
from app.services.homatics_compatibility import get_homatics_device_profile


def _file(*, video_codec="h264", hdr="SDR", dv_profile=None, audio_codec="ac3"):
    dolby_vision = SimpleNamespace(profile=dv_profile) if dv_profile else None
    video = SimpleNamespace(
        is_default=True,
        codec_name=video_codec,
        width=3840,
        height=2160,
        bit_depth=10,
        base_hdr_format=hdr,
        has_hdr10_plus=False,
        has_dolby_vision=bool(dv_profile),
        dolby_vision=dolby_vision,
    )
    audio = SimpleNamespace(is_default=True, codec_name=audio_codec)
    return SimpleNamespace(
        id="file-1",
        library_id="library-1",
        relative_path="Movie/Movie.mkv",
        container="matroska,webm",
        scan_status="complete",
        media_item=SimpleNamespace(title="Movie", year=2024),
        video_streams=[video],
        audio_streams=[audio],
        subtitle_streams=[],
    )


def test_shield_direct_plays_common_4k_file() -> None:
    profile = get_device_profile("nvidia-shield-tv-pro-2019")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", hdr="HDR10", audio_codec="truehd"), profile
    )

    assert result.outcome == "direct_play"


def test_apple_tv_requires_audio_conversion_for_truehd() -> None:
    profile = get_device_profile("apple-tv-4k-3rd-gen")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", hdr="HDR10", audio_codec="truehd"), profile
    )

    assert result.outcome == "audio_transcode"
    assert any(reason.code == "unsupported_audio_codec" for reason in result.reasons)


def test_fire_tv_profile_rejects_dolby_vision_profile_7() -> None:
    profile = get_device_profile("fire-tv-cube-3rd-gen")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="7", audio_codec="eac3"), profile
    )

    assert result.outcome == "video_transcode"
    assert any(
        reason.code == "unsupported_dolby_vision_profile"
        for reason in result.reasons
    )


def test_google_tv_streamer_accepts_av1_hdr10_plus() -> None:
    profile = get_google_tv_device_profile("google-tv-streamer-4k")
    assert profile is not None
    media_file = _file(video_codec="av1", hdr="HDR10", audio_codec="eac3")
    media_file.video_streams[0].has_hdr10_plus = True

    result = evaluate_file(media_file, profile)

    assert result.outcome == "direct_play"


def test_google_tv_streamer_requires_audio_conversion_for_truehd() -> None:
    profile = get_google_tv_device_profile("google-tv-streamer-4k")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", hdr="HDR10", audio_codec="truehd"), profile
    )

    assert result.outcome == "audio_transcode"
    assert any(reason.code == "unsupported_audio_codec" for reason in result.reasons)


def test_chromecast_with_google_tv_rejects_av1() -> None:
    profile = get_google_tv_device_profile("chromecast-with-google-tv-4k")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="av1", hdr="HDR10", audio_codec="eac3"), profile
    )

    assert result.outcome == "video_transcode"
    assert any(reason.code == "unsupported_video_codec" for reason in result.reasons)


def test_chromecast_with_google_tv_rejects_dolby_vision_profile_7() -> None:
    profile = get_google_tv_device_profile("chromecast-with-google-tv-4k")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="7", audio_codec="eac3"), profile
    )

    assert result.outcome == "video_transcode"
    assert any(
        reason.code == "unsupported_dolby_vision_profile"
        for reason in result.reasons
    )


def test_homatics_android_accepts_av1_hdr10_plus() -> None:
    profile = get_homatics_device_profile("homatics-box-r-4k-plus")
    assert profile is not None
    media_file = _file(video_codec="av1", hdr="HDR10", audio_codec="eac3")
    media_file.video_streams[0].has_hdr10_plus = True

    result = evaluate_file(media_file, profile)

    assert result.outcome == "direct_play"


def test_homatics_android_rejects_dolby_vision_profile_7() -> None:
    profile = get_homatics_device_profile("homatics-box-r-4k-plus")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="7", audio_codec="eac3"), profile
    )

    assert result.outcome == "video_transcode"
    assert any(
        reason.code == "unsupported_dolby_vision_profile"
        for reason in result.reasons
    )


def test_homatics_coreelec_accepts_dolby_vision_profile_7() -> None:
    profile = get_homatics_device_profile("homatics-box-r-4k-plus-coreelec")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="7", audio_codec="truehd"), profile
    )

    assert result.outcome == "direct_play"


def test_unknown_hdr_metadata_is_not_reported_as_direct_play() -> None:
    profile = get_device_profile("nvidia-shield-tv-pro-2019")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", hdr="UNKNOWN", audio_codec="ac3"), profile
    )

    assert result.outcome == "unknown"
    assert any(reason.code == "unknown_hdr_metadata" for reason in result.reasons)


def test_ugoos_am6b_plus_coreelec_accepts_dolby_vision_profile_7() -> None:
    profile = get_device_profile("ugoos-am6b-plus-coreelec")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="7", audio_codec="truehd"), profile
    )

    assert result.outcome == "direct_play"


def test_ugoos_sk1_accepts_av1_hdr10_plus() -> None:
    profile = get_device_profile("ugoos-sk1")
    assert profile is not None
    media_file = _file(video_codec="av1", hdr="HDR10", audio_codec="eac3")
    media_file.video_streams[0].has_hdr10_plus = True

    result = evaluate_file(media_file, profile)

    assert result.outcome == "direct_play"


def test_ugoos_am9_pro_rejects_dolby_vision() -> None:
    profile = get_device_profile("ugoos-am9-pro")
    assert profile is not None

    result = evaluate_file(
        _file(video_codec="hevc", dv_profile="8", audio_codec="eac3"), profile
    )

    assert result.outcome == "video_transcode"
    assert any(reason.code == "unsupported_hdr_format" for reason in result.reasons)


def test_ugoos_sk4_pro_accepts_av1_hdr10_plus() -> None:
    profile = get_device_profile("ugoos-sk4-pro")
    assert profile is not None
    media_file = _file(video_codec="av1", hdr="HDR10", audio_codec="eac3")
    media_file.video_streams[0].has_hdr10_plus = True

    result = evaluate_file(media_file, profile)

    assert result.outcome == "direct_play"
