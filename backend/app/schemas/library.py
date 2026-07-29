from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MediaKind, SourceType


class LibraryBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    media_kind: MediaKind = MediaKind.MIXED
    source_type: SourceType = SourceType.FILESYSTEM
    root_path: str = Field(min_length=1, max_length=2048)
    external_id: str | None = Field(default=None, max_length=255)
    enabled: bool = True


class LibraryCreate(LibraryBase):
    pass


class LibraryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    media_kind: MediaKind | None = None
    source_type: SourceType | None = None
    root_path: str | None = Field(default=None, min_length=1, max_length=2048)
    external_id: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None


class LibraryRead(LibraryBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    last_scan_at: datetime | None
