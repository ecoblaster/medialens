from __future__ import annotations

import re
from pathlib import Path

SUPPORTED_MEDIA_EXTENSIONS = {
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ts",
    ".vob",
    ".webm",
}

_IGNORED_DIRECTORY_NAMES = {
    "sample",
    "samples",
}

_IGNORED_EXACT_FILENAMES = {
    "rarbg.com.mp4",
    "rarbg.to.mp4",
    "www.rarbg.to.mp4",
    "www.yify-torrent.org.mp4",
    "www.yts.am.mp4",
    "www.yts.lt.mp4",
    "www.yts.mx.mp4",
}

_IGNORED_NAME_PARTS = {
    ".!qb",
}

_SAMPLE_TOKEN = re.compile(r"(?:^|[._\-\s])sample(?:[._\-\s]|$)", re.IGNORECASE)


def ignored_media_reason(path: Path) -> str | None:
    """Return why a path should not be treated as a library media item.

    The filter intentionally targets common download-client temporary names,
    release samples, and release-group promotional clips. It does not use a
    minimum file size because legitimate shorts and bonus material can be small.
    """

    if path.suffix.casefold() not in SUPPORTED_MEDIA_EXTENSIONS:
        return "unsupported_extension"

    directory_parts = [part.casefold() for part in path.parts[:-1]]
    if any(part in _IGNORED_DIRECTORY_NAMES for part in directory_parts):
        return "sample_directory"

    filename = path.name.casefold()
    if filename in _IGNORED_EXACT_FILENAMES:
        return "release_group_promo"

    if any(token in filename for token in _IGNORED_NAME_PARTS):
        return "temporary_download"

    if _SAMPLE_TOKEN.search(path.stem):
        return "sample_filename"

    return None


def is_supported_media_path(path: Path) -> bool:
    return ignored_media_reason(path) is None
