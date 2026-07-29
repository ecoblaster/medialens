from pathlib import Path

from app.services.normalizer import normalize_probe


def _base_ffprobe() -> dict:
    return {
        "format": {"format_name": "matroska", "duration": "10", "bit_rate": "1000"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "color_transfer": "smpte2084",
                "side_data_list": [],
            }
        ],
    }


def test_detects_hdr10_plus_from_mediainfo() -> None:
    mediainfo = {
        "media": {
            "track": [
                {
                    "@type": "Video",
                    "HDR_Format": "SMPTE ST 2094 App 4, Version 1, HDR10+ Profile B compatible",
                }
            ]
        }
    }

    normalized = normalize_probe(_base_ffprobe(), mediainfo, Path("movie.mkv"))

    assert normalized.videos[0].has_hdr10_plus is True


def test_detects_hdr10_plus_from_sampled_ffprobe_frames() -> None:
    ffprobe = _base_ffprobe()
    ffprobe["medialens_hdr10_plus_probe"] = {
        "frames": [
            {
                "stream_index": 0,
                "side_data_list": [
                    {"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}
                ],
            }
        ]
    }

    normalized = normalize_probe(ffprobe, {"media": {"track": []}}, Path("movie.mkv"))

    assert normalized.videos[0].has_hdr10_plus is True


def test_does_not_trust_filename_for_hdr10_plus() -> None:
    normalized = normalize_probe(
        _base_ffprobe(),
        {"media": {"track": []}},
        Path("Movie.HDR10+.mkv"),
    )

    assert normalized.videos[0].has_hdr10_plus is False
