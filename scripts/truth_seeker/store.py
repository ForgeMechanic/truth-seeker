"""One atomic authoritative snapshot: no half-written cross-file transactions."""
import copy
import os
import shutil
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from .errors import Conflict, TruthSeekerError
from .util import atomic_json, confined, read_json, write_utf8

COLLECTIONS = ("sources", "tests", "links", "decisions", "questions", "reviews", "todos", "runs")


def resources():
    return files("truth_seeker").joinpath("data")


def find_root(path):
    path = Path(path).expanduser().resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".truth-seeker" / "manifest.json").exists():
            return candidate
    raise TruthSeekerError("No .truth-seeker/manifest.json found; initialize or specify the consumer repository")


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.directory = self.root / ".truth-seeker"
        self.path = self.directory / "knowledge.json"
        if self.directory.is_symlink():
            raise TruthSeekerError("Knowledge directory must not be a symlink")

    @classmethod
    def initialize(cls, root):
        store = cls(root)
        if store.directory.exists():
            raise Conflict(".truth-seeker already exists; initialization never overwrites records")
        store.root.mkdir(parents=True, exist_ok=True)
        store.directory.mkdir()
        try:
            (store.directory / "schemas").mkdir()
            for name in ("knowledge.schema.json", "manifest.schema.json"):
                write_utf8(store.directory / "schemas" / name, resources().joinpath(name).read_text(encoding="utf-8-sig"))
            write_utf8(store.directory / "AGENTS.md", resources().joinpath("AGENTS.md").read_text(encoding="utf-8-sig"))
            state = {"format": "truth-seeker", "schemaVersion": 1, "generation": 0,
                     **{name: {} for name in COLLECTIONS}}
            store.validate(state)
            atomic_json(store.path, state)
            atomic_json(store.directory / "manifest.json", {"format": "truth-seeker", "schemaVersion": 1,
                        "data": "knowledge.json", "schemaRef": "schemas/knowledge.schema.json"})
        except BaseException:
            shutil.rmtree(store.directory)
            raise
        return store

    def load(self):
        manifest = read_json(self.directory / "manifest.json")
        # Fixed paths make independently readable data safe to load without following arbitrary refs.
        self._schema_validate(manifest, "manifest.schema.json")
        state = read_json(self.path)
        self.validate(state)
        return state

    def _schema_validate(self, value, name):
        schema = read_json(confined(self.directory, "schemas/" + name))
        # No remote resolution, including in edited schemas.
        def local_only(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    if key in ("$ref", "$dynamicRef") and not item.startswith("#"):
                        raise TruthSeekerError("Only local fragment schema references are supported")
                    local_only(item)
            elif isinstance(node, list):
                for item in node:
                    local_only(item)
        local_only(schema)
        try:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(value)
        except Exception as exc:
            raise TruthSeekerError(f"Invalid {name}: {exc}") from exc

    def validate(self, state):
        self._schema_validate(state, "knowledge.schema.json")
        def require(collection, key):
            if key not in state[collection]:
                raise TruthSeekerError(f"Missing {collection} reference: {key}")
        for collection in COLLECTIONS:
            for key, value in state[collection].items():
                if key != value["id"]:
                    raise TruthSeekerError(f"Record key differs from id: {collection}/{key}")
                for field, target in (("source_ids", "sources"), ("test_ids", "tests"),
                                      ("decision_ids", "decisions"), ("question_ids", "questions")):
                    for ref in value.get(field, []):
                        require(target, ref)
                for field, target in (("source_id", "sources"), ("test_id", "tests"),
                                      ("run_id", "runs"), ("review_id", "reviews"),
                                      ("closed_by", "reviews"), ("supersedes", "decisions"),
                                      ("superseded_by", "decisions")):
                    if field in value:
                        require(target, value[field])
                if collection in ("sources", "tests") and "path" in value:
                    confined(self.root, value["path"])
                if collection == "sources" and value["origin"] == "external":
                    parsed = urlsplit(value["url"])
                    if parsed.scheme not in ("https", "http", "file"):
                        raise TruthSeekerError("External source URL must use https, http or file")
                    if parsed.username or parsed.password or (parsed.scheme != "file" and not parsed.netloc):
                        raise TruthSeekerError("URL must identify an origin without embedded credentials")
        for run in state["runs"].values():
            for test_id, item in run["items"].items():
                require("tests", test_id)
                if "review_id" in item:
                    require("reviews", item["review_id"])
        for todo in state["todos"].values():
            if todo["status"] == "closed" and ("closed_by" not in todo or "closure_reason" not in todo):
                raise TruthSeekerError("Closed to-do needs a covering review and closure reason")

    @contextmanager
    def lock(self):
        lock = self.directory / ".write-lock"
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise Conflict("Writer lock exists. Check for a live writer before manually removing a stale lock") from exc
        try:
            write_utf8(lock / "owner", str(os.getpid()))
            yield
        finally:
            shutil.rmtree(lock)

    def update(self, operation, expected=None):
        with self.lock():
            state = self.load()
            if expected is not None and state["generation"] != expected:
                raise Conflict("Records changed since inspection; reload before writing")
            candidate = copy.deepcopy(state)
            result = operation(candidate)
            candidate["generation"] += 1
            self.validate(candidate)
            atomic_json(self.path, candidate)
            return result
