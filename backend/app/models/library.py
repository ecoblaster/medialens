from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid
from app.models.enums import MediaKind, SourceType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.media import MediaFile, MediaItem
    from app.models.scan import ScanRun


class Library(TimestampMixin, Base):
    __tablename__ = "libraries"
    __table_args__ = (
        UniqueConstraint("source_type", "root_path", name="source_root"),
        Index("ix_libraries_enabled", "enabled"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_kind: Mapped[str] = mapped_column(
        String(20), default=MediaKind.MIXED.value, nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(20), default=SourceType.FILESYSTEM.value, nullable=False
    )
    root_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    media_items: Mapped[list["MediaItem"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )
    media_files: Mapped[list["MediaFile"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )
    scan_runs: Mapped[list["ScanRun"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )
