"""
Shared data layer for Online Code Explorer.

Protocol-agnostic file operations over the project-root data/ directory.
The REST backend calls this module; it must not touch the disk itself.
This file must not import FastAPI.

Storage is flat: filenames are a single path segment under data/.
Maximum file size is 5MB. Encoding is UTF-8.
REST uses count_words() for the cached workspace word count.
"""

import os
from datetime import datetime, timezone
from typing import List, NamedTuple

# Resolve data/ from the project root (parent of backend/), independent of CWD.
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit for UTF-8 byte length
UNSAFE_FILENAME_CHARS = ("..", "/", "\\")


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class FileInfo(NamedTuple):
    """File metadata: name, size in bytes, last modified time (ISO 8601)."""

    name: str
    size: int
    last_modified: str


class FileContent(NamedTuple):
    """File body, always treated as UTF-8 text."""

    content: str


class SearchHit(NamedTuple):
    """One keyword match: filename and 1-based line number (Monaco-compatible)."""

    filename: str
    line_number: int


class FileSizeInfo(NamedTuple):
    """On-disk size for one regular file under data/."""

    name: str
    size: int


# ---------------------------------------------------------------------------
# Exceptions (mapped to HTTP / gRPC status codes by each protocol layer)
# ---------------------------------------------------------------------------


class InvalidFilenameError(Exception):
    """Raised when a filename is empty, reserved, or would escape data/."""

    def __init__(self, message: str = "Invalid filename") -> None:
        super().__init__(message)


class DataFileNotFoundError(Exception):
    """Raised when a read / update / delete targets a missing file."""

    def __init__(self, message: str = "File not found") -> None:
        super().__init__(message)


class DataFileExistsError(Exception):
    """Raised when create is asked to write a name that already exists."""

    def __init__(self, message: str = "File already exists") -> None:
        super().__init__(message)


class FileTooLargeError(Exception):
    """Raised when UTF-8 content exceeds MAX_FILE_SIZE."""

    def __init__(self, message: str = "File too large. Maximum size is 5MB.") -> None:
        super().__init__(message)


class InvalidUtf8Error(Exception):
    """Raised when an on-disk file cannot be decoded as UTF-8."""

    def __init__(self, message: str = "File is not valid UTF-8") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def ensure_data_dir() -> None:
    """Create data/ if it does not already exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _validate_filename(filename: str) -> None:
    """Reject empty, reserved, or traversal / separator names."""
    if (
        not filename
        or filename in (".", "..")
        or any(token in filename for token in UNSAFE_FILENAME_CHARS)
    ):
        raise InvalidFilenameError()


def _file_path(filename: str) -> str:
    """Join filename under data/ and ensure the result stays inside data/."""
    _validate_filename(filename)
    ensure_data_dir()
    path = os.path.realpath(os.path.join(DATA_DIR, filename))
    data_root = os.path.realpath(DATA_DIR)
    if os.path.commonpath([data_root, path]) != data_root:
        raise InvalidFilenameError()
    return path


def _build_file_info(filename: str, path: str) -> FileInfo:
    """Build FileInfo from os.path.getsize and os.path.getmtime."""
    mtime = os.path.getmtime(path)
    last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return FileInfo(
        name=filename,
        size=os.path.getsize(path),
        last_modified=last_modified,
    )


def _require_existing_file(filename: str) -> str:
    """Return the path if the name is a regular file; otherwise raise."""
    path = _file_path(filename)
    if not os.path.isfile(path):
        raise DataFileNotFoundError()
    return path


def _check_content_size(content: str) -> None:
    """Reject content whose UTF-8 byte length exceeds 5MB."""
    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        raise FileTooLargeError()


def _write_text_file(path: str, content: str) -> None:
    """Write (create or overwrite) a UTF-8 text file."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------


def list_files() -> List[FileInfo]:
    """Scan data/ for regular files and return them sorted by name."""
    ensure_data_dir()
    result: List[FileInfo] = []
    for name in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, name)
        if os.path.isfile(path):
            result.append(_build_file_info(name, path))
    return result


def read_file(filename: str) -> FileContent:
    """Return the UTF-8 contents of an existing file."""
    path = _require_existing_file(filename)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except UnicodeDecodeError:
        raise InvalidUtf8Error()
    return FileContent(content=content)


def create_file(filename: str, content: str) -> FileInfo:
    """Create a new file. Raises DataFileExistsError if the name is taken."""
    path = _file_path(filename)
    if os.path.exists(path):
        raise DataFileExistsError()
    _check_content_size(content)
    _write_text_file(path, content)
    return _build_file_info(filename, path)


def update_file(filename: str, content: str) -> FileInfo:
    """Overwrite an existing file. Raises DataFileNotFoundError if missing."""
    path = _require_existing_file(filename)
    _check_content_size(content)
    _write_text_file(path, content)
    return _build_file_info(filename, path)


def delete_file(filename: str) -> None:
    """Delete an existing file. Raises DataFileNotFoundError if missing."""
    path = _require_existing_file(filename)
    os.remove(path)


# ---------------------------------------------------------------------------
# Workspace stats (gRPC monitor)
# ---------------------------------------------------------------------------


def _regular_files():
    """Yield (name, path) for regular files in data/, sorted by name."""
    ensure_data_dir()
    for name in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, name)
        if os.path.isfile(path):
            yield name, path


def count_files() -> int:
    """(a) Number of regular files in data/."""
    return sum(1 for _ in _regular_files())


def count_lines() -> int:
    """(b) Total line count across UTF-8 files; skip invalid UTF-8."""
    total = 0
    for name, _path in _regular_files():
        try:
            content = read_file(name).content
        except InvalidUtf8Error:
            continue
        total += len(content.splitlines())
    return total


def count_bytes() -> int:
    """(c) Total on-disk size in bytes (sum of os.path.getsize)."""
    return sum(os.path.getsize(path) for _name, path in _regular_files())


def count_words() -> int:
    """Total whitespace-separated tokens across UTF-8 files; skip invalid UTF-8."""
    total = 0
    for name, _path in _regular_files():
        try:
            content = read_file(name).content
        except InvalidUtf8Error:
            continue
        total += len(content.split())
    return total


def top_k_files(k: int) -> List[FileSizeInfo]:
    """Return up to k files with the largest on-disk size, largest first.

    Ties are broken by filename ascending. If k <= 0, return [].
    If k is larger than the number of files, return all of them.
    """
    if k <= 0:
        return []
    ranked = sorted(
        (
            FileSizeInfo(name=name, size=os.path.getsize(path))
            for name, path in _regular_files()
        ),
        key=lambda item: (-item.size, item.name),
    )
    return ranked[:k]


# ---------------------------------------------------------------------------
# Keyword search (GraphQL)
# ---------------------------------------------------------------------------

# Caps so a huge workspace cannot flood the search overlay.
MAX_SEARCH_HITS = 50
MAX_SEARCH_HITS_PER_FILE = 10


def search_files(keyword: str) -> List[SearchHit]:
    """Return case-insensitive substring hits as (filename, line_number)."""
    if not keyword or not keyword.strip():
        return []

    needle = keyword.strip().lower()
    hits: List[SearchHit] = []

    for name, _path in _regular_files():
        try:
            content = read_file(name).content
        except InvalidUtf8Error:
            continue

        per_file = 0
        for line_number, line in enumerate(content.splitlines(), start=1):
            if needle not in line.lower():
                continue
            hits.append(SearchHit(filename=name, line_number=line_number))
            per_file += 1
            if per_file >= MAX_SEARCH_HITS_PER_FILE or len(hits) >= MAX_SEARCH_HITS:
                break

        if len(hits) >= MAX_SEARCH_HITS:
            break

    return hits
