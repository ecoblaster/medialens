from pathlib import Path

from app.services.library_watcher import (
    LibraryRuntime,
    LibraryWatcherManager,
    _is_supported,
)


def test_supported_media_extensions_are_watched() -> None:
    assert _is_supported(Path("Movie.mkv"))
    assert _is_supported(Path("Episode.S01E01.MP4"))
    assert _is_supported(Path("Disc/feature.m2ts"))


def test_temporary_and_non_media_files_are_ignored() -> None:
    assert not _is_supported(Path("Movie.mkv.part"))
    assert not _is_supported(Path("Movie.!qB.mkv"))
    assert not _is_supported(Path("Movie.sample.mkv"))
    assert not _is_supported(Path("poster.jpg"))


def test_duplicate_events_share_one_pending_entry(tmp_path: Path) -> None:
    manager = LibraryWatcherManager()
    runtime = LibraryRuntime(
        library_id="library-1",
        library_name="Movies",
        root_path=tmp_path,
    )
    manager._libraries[runtime.library_id] = runtime
    media_path = tmp_path / "Movie.mkv"
    media_path.write_bytes(b"test")

    manager.handle_path_event(runtime.library_id, media_path)
    manager.handle_path_event(runtime.library_id, media_path)

    status = manager.status()
    assert status.pending_files == 1
    assert status.libraries[0].pending_files == 1
    assert status.recent_activity[0].action == "detected"


def test_status_reports_configured_library(tmp_path: Path) -> None:
    manager = LibraryWatcherManager()
    manager._running = True
    manager._libraries["library-1"] = LibraryRuntime(
        library_id="library-1",
        library_name="TV Shows",
        root_path=tmp_path,
        state="reconciliation_only",
    )

    status = manager.status()

    assert status.running is True
    assert status.libraries[0].library_name == "TV Shows"
    assert status.libraries[0].state == "reconciliation_only"
