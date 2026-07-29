from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid
from app.models.enums import ScanFileStatus, ScanMode, ScanRunStatus

if TYPE_CHECKING:
    from app.models.library import Library
    from app.models.media import MediaFile, ProbeSnapshot


class ScanRun(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (
        Index("ix_scan_runs_library_status", "library_id", "status"),
        Index("ix_scan_runs_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(
        String(20), default=ScanMode.INCREMENTAL.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ScanRunStatus.QUEUED.value, nullable=False
    )
    requested_relative_path: Mapped[str | None] = mapped_column(String(4096))
    files_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str] = mapped_column(String(100), nullable=False)

    library: Mapped["Library"] = relationship(back_populates="scan_runs")
    file_results: Mapped[list["ScanFileResult"]] = relationship(
        back_populates="scan_run", cascade="all, delete-orphan"
    )
    probe_snapshots: Mapped[list["ProbeSnapshot"]] = relationship(
        back_populates="scan_run", cascade="all, delete-orphan"
    )


class ScanFileResult(Base):
    __tablename__ = "scan_file_results"
    __table_args__ = (Index("ix_scan_file_results_run_status", "scan_run_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scan_run_id: Mapped[str] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    media_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    relative_path: Mapped[str] = mapped_column(String(4096), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ScanFileStatus.ANALYZED.value, nullable=False
    )
    metadata_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    scan_run: Mapped[ScanRun] = relationship(back_populates="file_results")
    media_file: Mapped["MediaFile | None"] = relationship(back_populates="scan_results")
