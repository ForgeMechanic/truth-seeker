import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from truth_seeker.cache import Cache, default_root
from truth_seeker.documents import extract
from truth_seeker.errors import MissingEvidence, TruthSeekerError
from truth_seeker.service import Service
from truth_seeker.store import Store
from truth_seeker.util import digest


class Documents(unittest.TestCase):
    def test_line_endings_normalize_extracted_text_without_changing_artifact_identity(self):
        cases = [
            ("markdown", "# Contract\n## Rule\ncafé\n", {"heading_path": ["Contract", "Rule"]}),
            ("html", '<h1>Contract</h1>\n<h2 id="rule">Rule</h2>\n<p>café</p>\n', {"anchor": "rule"}),
            ("text", "class Suite:\n    def test_rule(self):\n        assert 'café'\n", {"python": "Suite.test_rule"}),
            ("text", "First\ncafé\nLast\n", {"lines": [2, 2]}),
        ]
        for kind, text, selector in cases:
            expected = extract(text.encode("utf-8"), kind, selector)
            for ending in ("\n", "\r\n", "\r"):
                with self.subTest(kind=kind, ending=repr(ending)):
                    data = text.replace("\n", ending).encode("utf-8")
                    actual = extract(data, kind, selector)
                    self.assertEqual(actual["text"], expected["text"])
                    self.assertEqual(actual["content_hash"], expected["content_hash"])
                    self.assertEqual(actual["artifact_hash"], digest(data))

    def test_markdown_path_disambiguates_and_fences_are_ignored(self):
        text = b"# One\n## Rule\nA\n# Two\n## Rule\nB\n```\n## Fake\n```\n"
        with self.assertRaises(MissingEvidence):
            extract(text, "markdown", {"heading": "Rule"})
        result = extract(text, "markdown", {"heading_path": ["Two", "Rule"]})
        self.assertIn("B", result["text"])
        with self.assertRaises(MissingEvidence):
            extract(text, "markdown", {"heading": "Fake"})
        self.assertEqual(result["artifact_hash"], digest(text))

    def test_python_symbols_include_decorators_and_nested_names(self):
        data = b"class Suite:\n    @decorator\n    def test_a(self):\n        assert True\n\ndef test_a():\n    assert False\n"
        result = extract(data, "text", {"python": "Suite.test_a"})
        self.assertIn("@decorator", result["text"])
        self.assertNotIn("False", result["text"])
        with self.assertRaises(MissingEvidence):
            extract(data, "text", {"python": "unknown"})

    def test_html_heading_anchor_and_duplicate_resolution(self):
        data = b'<h1>Contract</h1><h2 id="one">Rule</h2><p>first</p><script>ignore me</script><h2 id="two">Rule</h2><p>second</p>'
        with self.assertRaises(MissingEvidence):
            extract(data, "html", {"heading": "Rule"})
        result = extract(data, "html", {"anchor": "one"})
        self.assertIn("first", result["text"])
        self.assertNotIn("second", result["text"])
        self.assertNotIn("ignore", result["text"])

    def test_docx_heading_extracts_without_external_relationships(self):
        buffer = io.BytesIO()
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
        <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Contract</w:t></w:r></w:p>
        <w:p><w:r><w:t>Expected behavior</w:t></w:r></w:p>
        <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Other</w:t></w:r></w:p>
        <w:p><w:r><w:t>Unrelated</w:t></w:r></w:p></w:body></w:document>'''
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        result = extract(buffer.getvalue(), "docx", {"heading": "Contract"})
        self.assertIn("Expected behavior", result["text"])
        self.assertNotIn("Unrelated", result["text"])
        with self.assertRaises(MissingEvidence):
            extract(buffer.getvalue(), "docx", {"heading": "Missing"})

    def test_pdf_pages_and_bookmarks_are_tied_to_original_bytes(self):
        writer = PdfWriter()
        for text in ("First rule", "Second rule"):
            page = writer.add_blank_page(width=300, height=300)
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_outline_item("First", 0)
        writer.add_outline_item("Second", 1)
        buffer = io.BytesIO()
        writer.write(buffer)
        data = buffer.getvalue()
        page = extract(data, "pdf", {"pages": [2, 2]})
        self.assertIn("Second rule", page["text"])
        self.assertEqual(page["artifact_hash"], digest(data))
        self.assertIn("First rule", extract(data, "pdf", {"bookmark": "First"})["text"])
        with self.assertRaises(MissingEvidence):
            extract(data, "pdf", {"bookmark": "Missing"})

    def test_pdf_without_extractable_text_is_missing_evidence(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        buffer = io.BytesIO()
        writer.write(buffer)
        with self.assertRaises(MissingEvidence):
            extract(buffer.getvalue(), "pdf")

    def test_markdown_language_heading_keeps_literal_hash(self):
        self.assertIn("Rule", extract(b"# C#\nRule\n", "markdown", {"heading": "C#"})["text"])

    def test_invalid_and_legacy_documents_report_unsupported_evidence(self):
        with self.assertRaises(MissingEvidence):
            extract(b"# Contract\nRule", "markdown", {"heading": "Contract", "heading_path": ["Contract"]})
        for kind in ("pdf", "docx"):
            with self.subTest(kind=kind), self.assertRaises(MissingEvidence):
                extract(b"not a document", kind)
        with self.assertRaises(MissingEvidence):
            extract(b"text", "text", {"lines": [5, 10]})


class ExternalEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cache test ü ")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.store = Store.initialize(base / "repo")
        self.cache = Cache(self.store.root, base / "cache")
        self.service = Service(self.store, self.cache)
        (self.store.root / "test.py").write_text("assert True\n", encoding="utf-8")
        self.source = {"id": "external", "origin": "external", "url": "https://unreachable.invalid/spec.md",
                       "kind": "markdown", "role": "standard", "scope": "example", "edition": "1"}
        self.service.register("sources", self.source, approval="Use edition 1")
        self.service.register("tests", {"id": "t", "path": "test.py", "assertion": "Rule"})
        self.service.register("links", {"id": "l", "source_id": "external", "test_id": "t", "nature": "behavior",
                              "rationale": "Recorded relation", "status": "established"}, approval="Confirmed")

    def artifact(self, text):
        path = self.store.root.parent / "supplied document.md"
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_cache_only_existing_and_missing_evidence_never_contacts_network(self):
        scope = {"type": "test", "value": "t"}
        with patch("socket.socket", side_effect=AssertionError("Unexpected network")), patch("truth_seeker.cache.build_opener", side_effect=AssertionError("Unexpected acquisition")):
            self.assertEqual(self.service.start(scope)["items"]["t"]["status"], "blocked")
            imported = self.service.import_source("external", self.artifact("# Rule\nExpected"))
            self.assertEqual(self.service.start(scope)["items"]["t"]["status"], "pending")
            with self.assertRaises(TruthSeekerError):
                self.service.fetch_source("external")
            self.assertEqual(self.cache.read(imported["object_hash"]), b"# Rule\nExpected")

    def test_bad_hash_is_rejected_and_corruption_is_detected(self):
        path = self.artifact("Expected")
        with self.assertRaises(TruthSeekerError):
            self.service.import_source("external", path, expected_hash="0" * 64)
        source = self.service.import_source("external", path)
        (self.cache.root / "objects" / source["object_hash"]).write_bytes(b"Corrupt")
        with self.assertRaises(MissingEvidence):
            self.service.evidence.source(source)

    def test_import_preserves_crlf_bytes_and_uses_canonical_text_for_review(self):
        path = self.artifact("ignored")
        original = "# Rule\r\n规范 café\r\n".encode("utf-8")
        path.write_bytes(original)
        source = self.service.import_source("external", path, expected_hash=digest(original))
        self.assertEqual(self.cache.read(source["object_hash"]), original)
        extracted = self.service.evidence.source(source)
        self.assertEqual(extracted["text"], "# Rule\n规范 café\n")
        self.assertEqual(extracted["content_hash"], digest("# Rule\n规范 café\n".encode("utf-8")))
        self.assertEqual(extracted["artifact_hash"], digest(original))

    def test_empty_platform_cache_variables_use_user_defaults(self):
        home = self.store.root.parent / "user home"
        with patch.dict(os.environ, {"TRUTH_SEEKER_CACHE": "", "LOCALAPPDATA": "", "XDG_CACHE_HOME": ""}), patch("truth_seeker.cache.Path.home", return_value=home):
            for platform, relative in (("win32", "AppData/Local/truth-seeker/Cache"),
                                       ("darwin", "Library/Caches/truth-seeker"),
                                       ("linux", ".cache/truth-seeker")):
                with self.subTest(platform=platform), patch("truth_seeker.cache.sys.platform", platform):
                    self.assertEqual(default_root(), home / relative)

    def test_refresh_keeps_selected_version_and_review_baseline(self):
        source = self.service.import_source("external", self.artifact("# Rule\nOld"))
        scope = {"type": "test", "value": "t"}
        run = self.service.start(scope)
        packet = self.service.packet(run["id"], "t")
        review = self.service.complete(run["id"], "t", basis_hash=packet["basis_hash"], outcome="supported", reasoning="Compared", claim="Rule")
        observed = self.service.import_source("external", self.artifact("# Rule\nNew"))
        self.assertEqual(observed["object_hash"], source["object_hash"])
        self.assertNotEqual(observed["observed"]["object_hash"], source["object_hash"])
        self.assertEqual(self.service.plan(scope)["items"]["t"]["status"], "reused")
        self.service.import_source("external", self.artifact("# Rule\nNew"), adopt=True)
        self.assertEqual(self.service.plan(scope)["items"]["t"]["status"], "pending")
        self.assertEqual(self.store.load()["reviews"][review["id"]]["basis"], review["basis"])
        self.assertIn(b"Old", self.cache.read(source["object_hash"]))

    def test_read_only_shared_cache_and_offline_prepopulation(self):
        shared = Cache(self.store.root, self.store.root.parent / "shared")
        artifact = shared.import_bytes(self.source["url"], b"Prepopulated")
        reader = Cache(self.store.root, self.store.root.parent / "empty", [shared.root])
        self.assertEqual(reader.read(artifact["object_hash"]), b"Prepopulated")
        self.assertFalse(reader.root.exists())
        self.assertIsNone(artifact["retrieved_at"])

    def test_cache_inside_repository_and_credentials_are_rejected(self):
        with self.assertRaises(TruthSeekerError):
            Cache(self.store.root, self.store.root / ".cache")
        with self.assertRaises(TruthSeekerError):
            self.service.register("sources", {**self.source, "id": "credentials", "url": "https://name:password@example.com/doc"}, approval="User request")

    def test_relocating_url_preserves_identity_and_review(self):
        source = self.service.import_source("external", self.artifact("Rule"))
        changed = self.service.relocate("sources", "external", "https://new.invalid/rule", "Same source moved")
        self.assertEqual(changed["object_hash"], source["object_hash"])
        self.assertEqual(changed["id"], "external")
        self.assertEqual(self.service.evidence.source(changed)["text"], "Rule")

    def test_file_url_acquisition_is_explicit(self):
        path = self.artifact("Local file URL")
        with self.assertRaises(TruthSeekerError):
            self.cache.acquire(path.as_uri())
        result = self.cache.acquire(path.as_uri(), cache_only=False)
        self.assertEqual(self.cache.read(result["object_hash"]), b"Local file URL")

    def test_cache_subdirectory_symlink_cannot_write_into_consumer(self):
        self.cache.root.mkdir()
        try:
            (self.cache.root / "objects").symlink_to(self.store.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks is unavailable for this OS/user")
        before = set(self.store.root.iterdir())
        with self.assertRaises(TruthSeekerError):
            self.cache.import_bytes(self.source["url"], b"Must not enter consumer")
        self.assertEqual(set(self.store.root.iterdir()), before)

    def test_defaults_respect_configured_environment(self):
        with patch.dict(os.environ, {"TRUTH_SEEKER_CACHE": str(self.cache.root)}):
            self.assertEqual(default_root(), self.cache.root)


class Acquisition(unittest.TestCase):
    def test_http_conditional_refresh_and_failure_preserve_cache(self):
        class Handler(BaseHTTPRequestHandler):
            requests = []
            fail = False
            def do_GET(self):
                Handler.requests.append(dict(self.headers))
                if Handler.fail:
                    self.send_error(404)
                elif self.headers.get("If-None-Match") == '"v1"':
                    self.send_response(304)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("ETag", '"v1"')
                    self.end_headers()
                    self.wfile.write(b"Original spec")
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = Cache(root / "repo", root / "cache")
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/spec"
                first = cache.acquire(url, cache_only=False)
                again = cache.acquire(url, cache_only=False)
                self.assertEqual(first["object_hash"], again["object_hash"])
                self.assertEqual(Handler.requests[1]["If-None-Match"], '"v1"')
                Handler.fail = True
                with self.assertRaises(TruthSeekerError):
                    cache.acquire(url, cache_only=False)
                self.assertEqual(cache.read(first["object_hash"]), b"Original spec")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
