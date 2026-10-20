"""External bytes only; acquisition is explicit and unavailable to review code."""
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, url2pathname

from .errors import MissingEvidence, TruthSeekerError
from .util import atomic_json, digest, now, read_json

MAX_BYTES = 64 * 1024 * 1024


def default_root():
    if os.environ.get("TRUTH_SEEKER_CACHE"):
        return Path(os.environ["TRUTH_SEEKER_CACHE"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "truth-seeker" / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "truth-seeker"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "truth-seeker"


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme not in ("http", "https") or target.username or target.password:
            raise TruthSeekerError("Unsupported redirect destination")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class Cache:
    def __init__(self, repository, root=None, shared=()):
        repository = Path(repository).resolve()
        self.repository = repository
        self.root = Path(root or default_root()).expanduser().resolve()
        self.roots = [self.root, *(Path(p).expanduser().resolve() for p in shared)]
        if any(p.is_relative_to(repository) for p in self.roots):
            raise TruthSeekerError("External cache must be outside the consumer repository")

    def location(self, root, *parts):
        path = root.joinpath(*parts).resolve()
        if not path.is_relative_to(root) or path.is_relative_to(self.repository):
            raise TruthSeekerError("Cache symlink escapes its configured external root")
        return path

    def read(self, content_hash):
        if not isinstance(content_hash, str) or len(content_hash) != 64 or any(c not in "0123456789abcdef" for c in content_hash):
            raise MissingEvidence("No valid selected cache hash; explicitly import or select evidence")
        for root in self.roots:
            path = self.location(root, "objects", content_hash)
            if path.is_file():
                data = path.read_bytes()
                if digest(data) != content_hash:
                    raise MissingEvidence(f"Cache object hash mismatch: {content_hash}")
                return data
        raise MissingEvidence(f"Cache object unavailable: {content_hash}")

    def mapping(self, url):
        for root in self.roots:
            path = self.location(root, "origins", digest(url.encode()) + ".json")
            if path.is_file():
                return read_json(path)
        return None

    def import_bytes(self, url, data, *, expected_hash=None, retrieved_at=None, version=None,
                     etag=None, modified=None):
        actual = digest(data)
        if expected_hash is not None and actual != expected_hash:
            raise TruthSeekerError("Imported artifact does not match the expected SHA-256")
        if len(data) > MAX_BYTES:
            raise TruthSeekerError("Artifact exceeds 64 MiB limit")
        self.root.mkdir(parents=True, exist_ok=True)
        objects = self.location(self.root, "objects")
        objects.mkdir(exist_ok=True)
        target = self.location(self.root, "objects", actual)
        if target.exists():
            self.read(actual)
        else:
            with tempfile.NamedTemporaryFile(dir=objects, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                except BaseException:
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        metadata = {"url": url, "object_hash": actual, "retrieved_at": retrieved_at,
                    "checked_at": None, "version": version, "etag": etag, "last_modified": modified}
        # Each revision's provenance is independent, so older objects remain interpretable.
        atomic_json(self.location(self.root, "metadata", digest(url.encode()), actual + ".json"), metadata)
        atomic_json(self.location(self.root, "origins", digest(url.encode()) + ".json"), metadata)
        return metadata

    def acquire(self, url, *, cache_only=True, version=None, conditional=True):
        if cache_only:
            raise TruthSeekerError("Cache-only mode prohibits acquisition and all network checks")
        parsed = urlsplit(url)
        if parsed.username or parsed.password:
            raise TruthSeekerError("Do not embed credentials in source URLs")
        if parsed.scheme == "file":
            if parsed.netloc not in ("", "localhost"):
                raise TruthSeekerError("Remote file hosts are unsupported; use explicit local import")
            data = Path(url2pathname(parsed.path)).read_bytes()
            return self.import_bytes(url, data, retrieved_at=now(), version=version)
        if parsed.scheme not in ("http", "https"):
            raise TruthSeekerError("Acquisition supports http, https and local file URLs")
        old = self.mapping(url)
        headers = {"User-Agent": "Truth-Seeker/0.1"}
        if conditional and old:
            # Send validators only if their cached bytes still exist and pass integrity checks.
            try:
                self.read(old["object_hash"])
            except MissingEvidence:
                old = None
            if old:
                for field, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
                    if old.get(field):
                        headers[header] = old[field]
        try:
            with build_opener(RestrictedRedirect()).open(Request(url, headers=headers), timeout=30) as response:
                data = response.read(MAX_BYTES + 1)
                metadata = self.import_bytes(url, data, retrieved_at=now(), version=version,
                                             etag=response.headers.get("ETag"),
                                             modified=response.headers.get("Last-Modified"))
        except HTTPError as exc:
            exc.close()
            if exc.code != 304 or old is None:
                raise TruthSeekerError(f"Acquisition failed; existing cache retained: {exc}") from exc
            metadata = old
        except (OSError, ValueError) as exc:
            raise TruthSeekerError(f"Acquisition failed; existing cache retained: {exc}") from exc
        metadata["checked_at"] = now()
        atomic_json(self.location(self.root, "origins", digest(url.encode()) + ".json"), metadata)
        atomic_json(self.location(self.root, "metadata", digest(url.encode()), metadata["object_hash"] + ".json"), metadata)
        return metadata
