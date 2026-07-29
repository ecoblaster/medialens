from pathlib import Path

from app.services.media_paths import ignored_media_reason, is_supported_media_path


def test_normal_media_files_are_supported() -> None:
    assert is_supported_media_path(Path("Movies/The Big Sick (2017)/The.Big.Sick.2017.mkv"))
    assert is_supported_media_path(Path("TV/President Curtis/Season 1/S01E01.mkv"))


def test_sample_directories_are_ignored() -> None:
    path = Path(
        "TV/Batwoman/S3/Batwoman.S03E01.1080p.WEB.h264-GOSSIP/"
        "Sample/batwoman.s03e01.1080p.web.h264-gossip-sample.mkv"
    )
    assert ignored_media_reason(path) == "sample_directory"
    assert not is_supported_media_path(path)


def test_sample_filename_variants_are_ignored() -> None:
    assert not is_supported_media_path(Path("Movie.sample.mkv"))
    assert not is_supported_media_path(Path("Movie-sample.mkv"))
    assert not is_supported_media_path(Path("Movie_sample.mp4"))
    assert not is_supported_media_path(Path("sample.mkv"))


def test_release_group_promotional_video_is_ignored() -> None:
    path = Path(
        "Movies/Justice.League.Crisis.On.Two.Earths.2010.1080p.BluRay.H264.AAC-RARBG/"
        "RARBG.COM.mp4"
    )
    assert ignored_media_reason(path) == "release_group_promo"
    assert not is_supported_media_path(path)


def test_download_temporary_files_are_ignored() -> None:
    assert not is_supported_media_path(Path("Movie.!qB.mkv"))
    assert not is_supported_media_path(Path("Movie.mkv.part"))
