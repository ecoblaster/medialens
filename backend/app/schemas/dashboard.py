from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_files: int
    total_size_bytes: int
    scan_complete: int
    scan_failed: int
    hdr10: int
    hdr10_plus: int
    dolby_vision: int
    dolby_vision_profiles: dict[str, int]
    atmos: int
    dts_x: int
    hdr_formats: dict[str, int]
    video_codecs: dict[str, int]
    audio_formats: dict[str, int]
    resolutions: dict[str, int]
    library_health: dict[str, int]
