from typing import Literal

from pydantic import BaseModel

CompatibilityOutcome = Literal[
    "direct_play",
    "remux",
    "audio_transcode",
    "video_transcode",
    "unsupported",
    "unknown",
]
CompatibilityComponent = Literal[
    "container",
    "video",
    "hdr",
    "audio",
    "subtitle",
    "metadata",
]
CompatibilitySeverity = Literal["info", "warning", "error"]


class DeviceProfileRead(BaseModel):
    id: str
    name: str
    family: str
    description: str
    caveats: list[str]
    supported_containers: list[str]
    supported_video_codecs: list[str]
    supported_hdr_formats: list[str]
    supported_dolby_vision_profiles: list[str]
    supported_audio_codecs: list[str]
    supported_subtitle_codecs: list[str]
    maximum_width: int
    maximum_height: int
    maximum_bit_depth: int
    source_labels: list[str]


class CompatibilityReasonRead(BaseModel):
    component: CompatibilityComponent
    code: str
    message: str
    severity: CompatibilitySeverity


class FileCompatibilityRead(BaseModel):
    file_id: str
    library_id: str
    relative_path: str
    title: str
    year: int | None
    outcome: CompatibilityOutcome
    selected_container: str | None
    selected_video_codec: str | None
    selected_hdr_format: str | None
    selected_dolby_vision_profile: str | None
    selected_audio_codec: str | None
    selected_subtitle_codec: str | None
    reasons: list[CompatibilityReasonRead]


class CompatibilitySummaryRead(BaseModel):
    device: DeviceProfileRead
    total_files: int
    direct_play: int
    remux: int
    audio_transcode: int
    video_transcode: int
    unsupported: int
    unknown: int
    direct_play_percent: float
    issue_counts: dict[str, int]


class CompatibilityFileListRead(BaseModel):
    device: DeviceProfileRead
    total_matching: int
    files: list[FileCompatibilityRead]
