"""Exercise platform boundaries without weakening byte-identity checks."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from truth_seeker.cache import Cache
from truth_seeker.errors import TruthSeekerError
from truth_seeker.service import Service
from truth_seeker.store import Store, find_root, resources
from truth_seeker.util import atomic_json, confined, is_within, read_json, write_utf8


class Portability(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="portable ü ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_discovery_and_cache_guards_use_real_paths_through_aliases(self):
        repository = self.base / "consumer"
        store = Store.initialize(repository)
        (repository / "nested").mkdir()
        alias = self.base / "alias"
        try:
            alias.symlink_to(repository, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating directory aliases requires unavailable OS privileges")
        self.assertEqual(Store(alias).root, store.root)
        self.assertEqual(find_root(alias / "nested"), store.root)
        self.assertTrue(store.root.samefile(repository))
        cache = Cache(alias, self.base / "cache")
        self.assertEqual(cache.repository, store.root)
        with self.assertRaises(TruthSeekerError):
            Cache(alias, repository / "cache")
        with self.assertRaises(TruthSeekerError):
            Cache(repository, alias / "cache")

    def test_case_aliases_preserve_scope_and_cannot_hide_an_internal_cache(self):
        store = Store.initialize(self.base / "Project")
        alternate = self.base / "project"
        if not alternate.exists() or not alternate.samefile(store.root):
            self.skipTest("This volume has case-sensitive paths")
        self.assertTrue(is_within(store.root, alternate / "new cache"))
        with self.assertRaises(TruthSeekerError):
            Cache(store.root, alternate / "new cache")
        (store.root / "Tests").mkdir()
        (store.root / "Tests/case.py").write_bytes(b"assert True\n")
        service = Service(store, Cache(store.root, self.base / "external cache"))
        service.register("tests", {"id": "case", "path": "Tests/case.py", "assertion": "Case alias"})
        run = service.start({"type": "directory", "value": "tests"})
        self.assertEqual(set(run["items"]), {"case"})

    def test_case_sensitive_siblings_are_not_treated_as_aliases(self):
        store = Store.initialize(self.base / "Project")
        sibling = self.base / "project"
        if sibling.exists():
            self.skipTest("This volume has case-insensitive paths")
        sibling.mkdir()
        self.assertFalse(is_within(store.root, sibling / "cache"))
        Cache(store.root, sibling / "cache")
        with self.assertRaises(TruthSeekerError):
            confined(store.root, "../project/elsewhere")

    def test_initialization_normalizes_only_first_party_scaffolding(self):
        original = resources()
        supplied = self.base / "templates"
        supplied.mkdir()
        for name in ("knowledge.schema.json", "manifest.schema.json", "AGENTS.md"):
            text = original.joinpath(name).read_text(encoding="utf-8")
            (supplied / name).write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
        with patch("truth_seeker.store.resources", return_value=supplied):
            store = Store.initialize(self.base / "consumer")
        for name in ("schemas/knowledge.schema.json", "schemas/manifest.schema.json", "AGENTS.md"):
            data = (store.directory / name).read_bytes()
            self.assertNotIn(b"\r", data)
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(store.load()["generation"], 0)

    def test_json_reads_bom_and_crlf_but_writes_utf8_lf(self):
        path = self.base / "record.json"
        value = {"statement": "规范 café", "state": "unresolved"}
        supplied = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\r\n")
        path.write_bytes(b"\xef\xbb\xbf" + supplied.encode("utf-8"))
        self.assertEqual(read_json(path), value)
        atomic_json(path, value)
        data = path.read_bytes()
        self.assertNotIn(b"\r", data)
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("规范 café".encode("utf-8"), data)
        self.assertEqual(read_json(path), value)

    def test_first_party_text_output_is_lf_even_when_input_is_mixed(self):
        path = self.base / "instructions.md"
        write_utf8(path, "# 规范\r\nOne\rTwo\n")
        self.assertEqual(path.read_bytes(), "# 规范\nOne\nTwo\n".encode("utf-8"))

    def test_home_relative_roots_inputs_and_imports_resolve_consistently(self):
        home = self.base / "user home"
        home.mkdir()
        source = {"id": "remote", "origin": "external", "url": "https://example.invalid/spec.md",
                  "kind": "markdown", "role": "contract", "scope": "example"}
        (home / "source.json").write_bytes(json.dumps(source).encode("utf-8"))
        artifact = b"# Contract\r\nOriginal bytes\r\n"
        (home / "document.md").write_bytes(artifact)
        original_expanduser = os.path.expanduser

        def expanduser(value):
            return str(home) if value == "~" else original_expanduser(value)

        with patch("os.path.expanduser", side_effect=expanduser):
            store = Store.initialize("~/consumer")
            cache = Cache("~/consumer", "~/cache")
            service = Service(store, cache)
            service.register("sources", read_json("~/source.json"), approval="User selected contract")
            imported = service.import_source("remote", "~/document.md")
            self.assertEqual(store.root, (home / "consumer").resolve())
            self.assertEqual(find_root("~/consumer"), store.root)
            self.assertEqual(cache.repository, store.root)
            self.assertEqual(cache.read(imported["object_hash"]), artifact)

    def test_bundle_validation_ignores_line_endings_but_detects_schema_changes(self):
        checkout = Path(__file__).resolve().parents[1]
        copied = self.base / "source checkout"
        copied.mkdir()
        for name in ("SKILL.md", "README.md", "LICENSE"):
            shutil.copyfile(checkout / name, copied / name)
        for name in ("references", "specs", "schemas", "templates"):
            shutil.copytree(checkout / name, copied / name)
        (copied / "scripts").mkdir()
        shutil.copyfile(checkout / "scripts/validate-skill.py", copied / "scripts/validate-skill.py")
        shutil.copytree(checkout / "scripts/truth_seeker", copied / "scripts/truth_seeker",
                        ignore=shutil.ignore_patterns("__pycache__"))
        schema_path = copied / "schemas/knowledge.schema.json"
        for path in (schema_path, copied / "templates/AGENTS.md"):
            path.write_bytes(b"\xef\xbb\xbf" + path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
        command = [sys.executable, str(copied / "scripts/validate-skill.py")]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        schema = read_json(schema_path)
        schema["properties"]["generation"]["minimum"] = -1
        atomic_json(schema_path, schema)
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Bundled schema drift", result.stderr)


if __name__ == "__main__":
    unittest.main()
