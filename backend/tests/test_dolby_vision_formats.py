from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.library import Library
from app.models.media import DolbyVisionMetadata, MediaFile, MediaItem, VideoStream
from app.services.normalizer import normalize_probe


def _media_file(
    library: Library,
    *,
    title: str,
    profile: str,
    compatibility_id: int | None = None,
    el_type: str = "NONE",
) -> MediaFile:
    stream = VideoStream(
        stream_index=0,
        codec_name="hevc",
        width=3840,
        height=2160,
        base_hdr_format="HDR10",
        has_hdr10_plus=False,
        has_dolby_vision=True,
        dolby_vision=DolbyVisionMetadata(
            profile=profile,
            compatibility_id=compatibility_id,
            bl_present=True,
            el_present=profile == "7",
            rpu_present=True,
            el_type=el_type,
            detected_by="test",
        ),
    )
    return MediaFile(
        library=library,
        media_item=MediaItem(library=library, item_type="movie", title=title),
        relative_path=f"{title}.mkv",
        filename=f"{title}.mkv",
        scan_status="complete",
        video_streams=[stream],
    )


@pytest.mark.parametrize(
    ("dolby_vision_format", "expected_title"),
    [
        ("4", "Profile 4"),
        ("5", "Profile 5"),
        ("7-fel", "Profile 7 FEL"),
        ("7-mel", "Profile 7 MEL"),
        ("8.1", "Profile 8.1"),
        ("8.4", "Profile 8.4"),
    ],
)
def test_filters_files_by_dolby_vision_format(
    client: TestClient,
    db_session: Session,
    dolby_vision_format: str,
    expected_title: str,
) -> None:
    library = Library(
        name="Movies",
        media_kind="movies",
        source_type="filesystem",
        root_path="/media/movies",
    )
    db_session.add_all(
        [
            _media_file(library, title="Profile 4", profile="4"),
            _media_file(library, title="Profile 5", profile="5"),
            _media_file(library, title="Profile 7 FEL", profile="7", el_type="FEL"),
            _media_file(library, title="Profile 7 MEL", profile="7", el_type="MEL"),
            _media_file(
                library, title="Profile 8.1", profile="8", compatibility_id=1
            ),
            _media_file(
                library, title="Profile 8.4", profile="8", compatibility_id=4
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/files", params={"dolby_vision_format": dolby_vision_format}
    )

    assert response.status_code == 200
    assert [media_file["media_item"]["title"] for media_file in response.json()] == [
        expected_title
    ]


@pytest.mark.parametrize("el_type", ["FEL", "MEL"])
def test_normalizer_reads_profile_7_enhancement_layer_from_mediainfo(
    el_type: str,
) -> None:
    ffprobe = {
        "format": {"format_name": "matroska"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "side_data_list": [
                    {
                        "side_data_type": "DOVI configuration record",
                        "dv_profile": 7,
                        "dv_level": 6,
                        "rpu_present_flag": 1,
                        "el_present_flag": 1,
                        "bl_present_flag": 1,
                        "dv_bl_signal_compatibility_id": 6,
                    }
                ],
            }
        ],
    }
    mediainfo = {
        "media": {
            "track": [
                {
                    "@type": "Video",
                    "HDR_Format_Profile": "dvhe.07.06",
                    "HDR_Format_Settings": f"BL+{el_type}+RPU",
                }
            ]
        }
    }

    normalized = normalize_probe(ffprobe, mediainfo, Path("movie.mkv"))
    dolby_vision = normalized.videos[0].dolby_vision

    assert dolby_vision is not None
    assert dolby_vision.el_type == el_type
    assert dolby_vision.detected_by == "ffprobe+mediainfo"
