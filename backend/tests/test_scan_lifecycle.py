from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.scanner as scanner_module
from app.db.session import SessionLocal
from app.models.library import Library
from app.models.scan import ScanRun
from app.services.scanner import scan_single_file


def test_single_file_scan_publishes_discovered_count_before_probe(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_path = tmp_path / "movie.mkv"
    media_path.write_bytes(b"test media")
    library = Library(
        name="Movies",
        media_kind="movies",
        source_type="filesystem",
        root_path=str(tmp_path),
    )
    db_session.add(library)
    db_session.commit()

    observed_discovered: list[int] = []

    def inspect_running_scan(_: Path) -> None:
        with SessionLocal() as status_db:
            scan = status_db.scalar(select(ScanRun).order_by(ScanRun.started_at.desc()))
            assert scan is not None
            observed_discovered.append(scan.files_discovered)
        raise RuntimeError("Stop after observing the published scan state")

    monkeypatch.setattr(scanner_module, "probe_media", inspect_running_scan)

    scan = scan_single_file(db_session, library, media_path.name)

    assert observed_discovered == [1]
    assert scan.status == "failed"
