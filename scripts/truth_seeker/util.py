"""Portable identities, confined paths and atomic JSON writes."""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from .errors import TruthSeekerError


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    if not isinstance(data, bytes):
        data = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise TruthSeekerError(f"Cannot read JSON {path}: {exc}") from exc


def normalize_newlines(text):
    """Canonical extracted text; never use this on original artifact bytes."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_utf8(path, text):
    """Write first-party text consistently regardless of the OS newline default."""
    Path(path).write_text(normalize_newlines(text), encoding="utf-8", newline="\n")


def configure_output():
    """Keep the CLI's redirected JSON and reports UTF-8 on Windows as well."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False, newline="\n") as stream:
            name = stream.name
            json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def is_within(root, path):
    """Check ancestry using filesystem identity when path spellings differ."""
    root = Path(root).expanduser().resolve()
    path = Path(path).expanduser().resolve()
    if path.is_relative_to(root):
        return True
    try:
        root_stat = root.stat()
    except FileNotFoundError:
        return False
    for ancestor in (path, *path.parents):
        try:
            if os.path.samestat(ancestor.stat(), root_stat):
                return True
        except FileNotFoundError:
            continue
    return False


def confined(root, relative):
    """Reject absolute, escaping and symlink-escaping consumer locators on every OS."""
    relative = str(relative)
    if "\\" in relative or PureWindowsPath(relative).drive or relative.startswith("/"):
        raise TruthSeekerError("Use a repository-relative path with forward slashes")
    root = Path(root).expanduser().resolve()
    target = (root / relative).resolve()
    if not is_within(root, target):
        raise TruthSeekerError("Path escapes repository")
    return target
