"""Portable identities, confined paths and atomic JSON writes."""
import hashlib
import json
import os
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
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TruthSeekerError(f"Cannot read JSON {path}: {exc}") from exc


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


def confined(root, relative):
    """Reject absolute, escaping and symlink-escaping consumer locators on every OS."""
    relative = str(relative)
    if "\\" in relative or PureWindowsPath(relative).drive or relative.startswith("/"):
        raise TruthSeekerError("Use a repository-relative path with forward slashes")
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise TruthSeekerError("Path escapes repository")
    return target
