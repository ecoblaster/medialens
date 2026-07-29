from enum import StrEnum


class MediaKind(StrEnum):
    MOVIES = "movies"
    TV = "tv"
    MIXED = "mixed"


class SourceType(StrEnum):
    FILESYSTEM = "filesystem"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"


class ItemType(StrEnum):
    MOVIE = "movie"
    SHOW = "show"
    SEASON = "season"
    EPISODE = "episode"
    UNKNOWN = "unknown"


class FileScanStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class BaseHdrFormat(StrEnum):
    SDR = "SDR"
    HDR10 = "HDR10"
    HLG = "HLG"
    UNKNOWN = "UNKNOWN"


class DolbyVisionEnhancementLayer(StrEnum):
    FEL = "FEL"
    MEL = "MEL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class ImmersiveFormat(StrEnum):
    NONE = "NONE"
    DOLBY_ATMOS = "DOLBY_ATMOS"
    DTS_X = "DTS_X"
    AURO_3D = "AURO_3D"
    UNKNOWN = "UNKNOWN"


class SubtitleFormatClass(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


class ScanMode(StrEnum):
    SINGLE_FILE = "single_file"
    INCREMENTAL = "incremental"
    FULL = "full"


class ScanRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanFileStatus(StrEnum):
    ANALYZED = "analyzed"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
