"""Observable lifecycle and integration invariants, using isolated consumer repositories."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from truth_seeker.cache import Cache
from truth_seeker.cli import compact, main, markdown_report
from truth_seeker.errors import Conflict, MissingEvidence, TruthSeekerError
from truth_seeker.service import Service
from truth_seeker.store import Store, find_root
from truth_seeker.util import digest

SCOPE = {"type": "repository", "value": "."}


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="truth seeker ü ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "consumer repo ü"
        self.store = Store.initialize(self.root)
        self.cache = Cache(self.root, self.base / "external cache")
        self.service = Service(self.store, self.cache)
        (self.root / "tests").mkdir()
        (self.root / "spec.md").write_text("# Contract\n## A\nReturn 1.\n## B\nReturn 2.\n", encoding="utf-8")
        self.test_path = self.root / "tests" / "test_example.py"
        self.test_path.write_text("def test_a():\n    assert 1 == 1\n\ndef test_b():\n    assert 2 == 2\n", encoding="utf-8")
        self.service.register("sources", {"id": "spec", "origin": "repository", "path": "spec.md",
                              "kind": "markdown", "role": "project contract", "scope": "example"}, approval="Use our local contract")
        for name in ("a", "b"):
            self.service.register("tests", {"id": name, "path": "tests/test_example.py", "selector": {"python": "test_" + name}, "assertion": "Return " + ("1" if name == "a" else "2")})
            self.service.register("links", {"id": "link-" + name, "test_id": name, "source_id": "spec",
                                  "selector": {"heading": name.upper()}, "nature": "behavior", "rationale": "User identified matching contract", "status": "established"}, approval="These are the matching sections")

    def run_for(self, test="a", fresh=False):
        return self.service.start({"type": "test", "value": test}, fresh)

    def finish(self, run=None, test="a", outcome="supported", claim="Return the documented value", decisions=(), questions=()):
        run = run or self.run_for(test)
        packet = self.service.packet(run["id"], test)
        return self.service.complete(run["id"], test, basis_hash=packet["basis_hash"], outcome=outcome,
                                     reasoning="Compared the assertion with the recorded contract", claim=claim,
                                     decision_ids=decisions, question_ids=questions)

    def decision(self, key="d", sources=("spec",), tests=("a",)):
        record = {"id": key, "statement": "Intentional difference", "rationale": "Compatibility requirement",
                  "test_ids": list(tests), "source_ids": list(sources), "status": "proposed"}
        self.service.register("decisions", record)
        return self.service.accept_decision(key, "User accepts this difference")

    def test_initialize_is_readable_and_non_destructive(self):
        self.assertEqual(find_root(self.root / "tests"), self.store.root)
        self.assertTrue(find_root(self.root / "tests").samefile(self.root))
        self.assertTrue((self.store.directory / "schemas/knowledge.schema.json").is_file())
        self.assertTrue((self.store.directory / "AGENTS.md").is_file())
        self.assertFalse((self.root / "AGENTS.md").exists())
        with self.assertRaises(Conflict):
            Store.initialize(self.root)

    def test_invalid_update_preserves_bytes(self):
        before = self.store.path.read_bytes()
        with self.assertRaises(TruthSeekerError):
            self.store.update(lambda s: s["links"]["link-a"].update(source_id="missing"))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse((self.store.directory / ".write-lock").exists())

    def test_stale_generation_and_live_lock_reject_writes(self):
        with self.assertRaises(Conflict):
            self.store.update(lambda s: None, expected=0)
        with self.store.lock():
            with self.assertRaises(Conflict):
                self.store.update(lambda s: None)

    def test_failed_atomic_replace_preserves_previous_snapshot(self):
        before = self.store.path.read_bytes()
        with patch("truth_seeker.util.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.store.update(lambda s: None)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(list(self.store.directory.glob(".knowledge.json.*")))

    def test_unknown_format_rejected(self):
        with self.assertRaises(TruthSeekerError):
            self.store.update(lambda s: s.update(schemaVersion=2))

    def test_remote_schema_reference_is_never_resolved(self):
        schema = self.store.directory / "schemas/knowledge.schema.json"
        schema.write_text('{"$ref":"https://invalid.example/schema"}', encoding="utf-8")
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            with self.assertRaises(TruthSeekerError):
                self.store.load()

    def test_section_change_only_selects_recorded_dependents(self):
        run = self.service.start(SCOPE)
        self.finish(run, "a")
        self.finish(run, "b")
        self.assertEqual(self.service.plan(SCOPE)["items"]["a"]["status"], "reused")
        (self.root / "spec.md").write_text("# Contract\n## A\nReturn 9.\n## B\nReturn 2.\n", encoding="utf-8")
        result = self.service.plan(SCOPE)["items"]
        self.assertEqual(result["a"]["status"], "pending")
        self.assertEqual(result["b"]["status"], "reused")

    def test_document_relationship_reopens_on_any_document_change(self):
        self.store.update(lambda s: s["links"]["link-b"].pop("selector"))
        self.finish(test="b")
        with (self.root / "spec.md").open("a", encoding="utf-8") as stream:
            stream.write("\nNew section.\n")
        self.assertEqual(self.service.plan(SCOPE)["items"]["b"]["status"], "pending")

    def test_implementation_only_and_unrelated_test_changes_reuse(self):
        self.finish()
        (self.root / "implementation.py").write_text("changed = True\n", encoding="utf-8")
        self.test_path.write_text(self.test_path.read_text().replace("2 == 2", "3 == 3"), encoding="utf-8")
        self.assertEqual(self.service.plan(SCOPE)["items"]["a"]["status"], "reused")
        self.test_path.write_text(self.test_path.read_text().replace("1 == 1", "4 == 4"), encoding="utf-8")
        self.assertEqual(self.service.plan(SCOPE)["items"]["a"]["status"], "pending")

    def test_fresh_review_reexamines_without_overwriting_history(self):
        old = self.finish()
        run = self.run_for(fresh=True)
        self.assertEqual(run["items"]["a"]["status"], "pending")
        self.finish(run)
        self.assertIn(old["id"], self.store.load()["reviews"])
        self.assertEqual(len(self.store.load()["reviews"]), 2)

    def test_scope_is_a_hard_boundary(self):
        run = self.run_for()
        self.assertEqual(set(run["items"]), {"a"})
        with self.assertRaises(TruthSeekerError):
            self.service.packet(run["id"], "b")
        with self.assertRaises(TruthSeekerError):
            self.finish(run, "b")
        self.assertEqual(set(self.service.start({"type": "directory", "value": "tests"})["items"]), {"a", "b"})
        with self.assertRaises(TruthSeekerError):
            self.service.start({"type": "directory", "value": "../"})

    def test_packet_cannot_be_completed_after_inputs_change(self):
        run = self.run_for()
        packet = self.service.packet(run["id"], "a")
        self.test_path.write_text(self.test_path.read_text().replace("1 == 1", "8 == 8"), encoding="utf-8")
        with self.assertRaises(Conflict):
            self.service.complete(run["id"], "a", basis_hash=packet["basis_hash"], outcome="supported", reasoning="old", claim="old")
        self.assertEqual(self.store.load()["reviews"], {})

    def test_resume_reuses_completed_work_only(self):
        run = self.service.start(SCOPE)
        self.finish(run, "a")
        restarted = Service(Store(self.root), self.cache)
        planned = restarted.plan(SCOPE)["items"]
        self.assertEqual(planned["a"]["status"], "reused")
        self.assertEqual(planned["b"]["status"], "pending")
        report = restarted.report(run["id"])
        self.assertEqual(report["reviewed"], ["a"])
        self.assertEqual(report["unfinished"], ["b"])

    def test_unlinked_test_is_not_a_reported_gap(self):
        self.service.register("tests", {"id": "unlinked", "path": "tests/test_example.py", "assertion": "Extra feature"})
        run = self.service.start(SCOPE)
        self.assertEqual(run["items"]["unlinked"]["status"], "unlinked")
        report = self.service.report(run["id"])
        self.assertEqual(report["unavailable"], [])
        self.assertNotIn("unlinked", report["unfinished"])

    def test_missing_source_is_reported_without_deletion(self):
        self.finish()
        (self.root / "spec.md").unlink()
        run = self.run_for()
        self.assertEqual(run["items"]["a"]["status"], "blocked")
        self.assertIn("spec", self.store.load()["sources"])
        self.assertEqual(len(self.store.load()["reviews"]), 1)
        self.assertEqual(len(self.service.report(run["id"])["unavailable"]), 1)
        with self.assertRaises(TruthSeekerError):
            self.finish(run)

    def test_duplicate_heading_blocks_instead_of_guessing(self):
        (self.root / "spec.md").write_text("## A\nOne\n## A\nTwo\n", encoding="utf-8")
        self.assertEqual(self.run_for()["items"]["a"]["status"], "blocked")

    def test_explicit_source_and_relationship_establishment(self):
        with self.assertRaises(TruthSeekerError):
            self.service.register("sources", {"id": "other"})
        record = {"id": "proposal", "test_id": "a", "source_id": "spec", "nature": "architecture", "rationale": "Potential ownership"}
        self.service.register("links", record)
        self.assertNotIn("proposal", self.service.plan(SCOPE)["items"]["a"]["basis"]["links"])
        self.service.establish_link("proposal", "User confirms the architectural relationship")
        self.assertIn("proposal", self.service.plan(SCOPE)["items"]["a"]["basis"]["links"])

    def test_questions_are_not_repeated_without_relevant_change(self):
        self.service.record_question("q", "Which behavior is intended?", ["a"])
        self.assertFalse(self.service.questions()[0]["ask_again"])
        with self.assertRaises(Conflict):
            self.service.mark_asked("q")
        (self.root / "unrelated.md").write_text("unrelated", encoding="utf-8")
        self.assertFalse(self.service.questions()[0]["ask_again"])
        self.decision()
        self.assertTrue(self.service.questions()[0]["ask_again"])
        self.service.mark_asked("q")
        self.assertFalse(self.service.questions()[0]["ask_again"])
        self.assertTrue(self.service.questions(requested=True)[0]["ask_again"])

    def test_unanswered_question_does_not_settle_dependents_or_block_other_work(self):
        self.service.record_question("q", "Which contract?", ["a"])
        run = self.service.start(SCOPE)
        with self.assertRaises(TruthSeekerError):
            self.finish(run, questions=["q"])
        self.finish(run, outcome="ambiguous", questions=["q"])
        self.finish(run, "b")
        self.assertEqual(set(self.service.report(run["id"])["reviewed"]), {"a", "b"})
        self.service.answer("q", "Use the project contract", "User's answer")
        self.assertEqual(self.service.questions(), [])

    def test_explicit_test_scope_limits_decisions_and_questions_sharing_sources(self):
        self.decision(tests=["a"])
        self.service.record_question("q", "Only test A's issue", ["a"], ["spec"])
        run = self.run_for("b")
        packet = self.service.packet(run["id"], "b")
        self.assertEqual(packet["decisions"], {})
        self.assertEqual(packet["questions"], [])
        self.assertEqual(self.service.report(run["id"])["questions"], [])

    def test_decision_changes_trigger_reconsideration_and_preserve_history(self):
        self.decision()
        self.finish(decisions=["d"])
        replacement = {"id": "d2", "statement": "Revised choice", "rationale": "New compatibility target", "test_ids": ["a"], "source_ids": ["spec"]}
        with self.assertRaises(TruthSeekerError):
            self.service.supersede("d", replacement, "")
        self.service.supersede("d", replacement, "User approves changing target")
        decisions = self.store.load()["decisions"]
        self.assertEqual(decisions["d"]["status"], "superseded")
        self.assertEqual(decisions["d"]["rationale"], "Compatibility requirement")
        self.assertEqual(decisions["d2"]["supersedes"], "d")
        self.assertEqual(self.run_for()["items"]["a"]["status"], "pending")

    def test_decided_discrepancy_does_not_create_actions(self):
        self.decision()
        review = self.finish(outcome="contradiction", decisions=["d"])
        with self.assertRaises(Conflict):
            self.service.todo(review["id"], "Known difference")
        run = self.run_for(fresh=True)
        self.finish(run, outcome="contradiction", decisions=["d"])
        self.assertEqual(self.store.load()["decisions"]["d"]["status"], "accepted")
        self.assertEqual(self.service.report(run["id"])["actions"], [])

    def test_fixed_todo_closes_and_rediscovery_does_not_reopen(self):
        old = self.finish(outcome="contradiction")
        todo = self.service.todo(old["id"], "Return value conflicts")
        newer = self.finish(self.run_for(fresh=True))
        self.service.close_todo(todo["id"], newer["id"], "Later review confirms alignment")
        repeated = self.service.todo(old["id"], "Return value conflicts")
        self.assertEqual(repeated["id"], todo["id"])
        self.assertEqual(repeated["status"], "closed")

    def test_todo_closure_requires_covering_current_review(self):
        old = self.finish(outcome="contradiction")
        todo = self.service.todo(old["id"], "Conflict")
        other = self.finish(test="b")
        with self.assertRaises(TruthSeekerError):
            self.service.close_todo(todo["id"], other["id"], "Wrong scope")
        wrong_claim = self.finish(self.run_for(fresh=True), claim="Unrelated claim")
        with self.assertRaises(TruthSeekerError):
            self.service.close_todo(todo["id"], wrong_claim["id"], "Wrong claim")

    def test_identity_transfer_requires_establishment(self):
        self.finish()
        self.test_path.rename(self.root / "tests" / "moved ü.py")
        with self.assertRaises(TruthSeekerError):
            self.service.relocate("tests", "a", "tests/moved ü.py")
        self.service.relocate("tests", "a", "tests/moved ü.py", "User confirms same test")
        self.assertEqual(self.run_for()["items"]["a"]["status"], "reused")

    def test_removing_one_of_three_sources_preserves_decision(self):
        for source_id in ("s2", "s3"):
            self.service.register("sources", {"id": source_id, "origin": "repository", "path": "spec.md", "kind": "markdown", "role": "contract", "scope": "example"}, approval="Add source")
        self.decision(sources=["spec", "s2", "s3"])
        preview = self.service.removal_preview("spec")
        self.assertEqual(preview["count"], 0)
        self.service.remove_source("spec", token=preview["confirmation_token"])
        state = self.store.load()
        self.assertNotIn("spec", state["sources"])
        self.assertEqual(state["decisions"]["d"]["source_ids"], ["s2", "s3"])
        self.assertEqual(state["decisions"]["d"]["rationale"], "Compatibility requirement")

    def test_last_source_requires_current_impact_confirmation_and_preserves_decision(self):
        self.decision()
        preview = self.service.removal_preview("spec")
        self.assertEqual(preview["decisions_losing_last_source"], ["d"])
        with self.assertRaises(Conflict):
            self.service.remove_source("spec", token=preview["confirmation_token"])
        self.service.record_question("q", "Unrelated user question", ["b"])
        with self.assertRaises(Conflict):
            self.service.remove_source("spec", token=preview["confirmation_token"], confirmation="Proceed")
        preview = self.service.removal_preview("spec")
        self.service.remove_source("spec", token=preview["confirmation_token"], confirmation="User confirms this impact")
        state = self.store.load()
        self.assertEqual(state["decisions"]["d"]["source_ids"], [])
        self.assertEqual(state["decisions"]["d"]["status"], "accepted")
        self.assertTrue(any("no remaining sources" in q["text"] for q in state["questions"].values()))

    def test_unrelated_source_removal_does_not_suppress_changed_question(self):
        self.service.record_question("q", "Intent for A?", ["a"])
        self.decision()
        self.assertTrue(self.service.questions()[0]["ask_again"])
        self.service.register("sources", {"id": "unused", "origin": "repository", "path": "spec.md", "kind": "markdown", "role": "context", "scope": "other"}, approval="Previously selected")
        preview = self.service.removal_preview("unused")
        self.service.remove_source("unused", token=preview["confirmation_token"])
        self.assertTrue(self.service.questions()[0]["ask_again"])

    def test_source_only_review_history_is_removed_but_decision_is_not(self):
        self.decision()
        review = self.finish(decisions=["d"])
        preview = self.service.removal_preview("spec")
        self.service.remove_source("spec", token=preview["confirmation_token"], confirmation="Remove last source")
        state = self.store.load()
        self.assertNotIn(review["id"], state["reviews"])
        self.assertIn("d", state["decisions"])
        self.assertTrue(any(q["ask_again"] for q in self.service.questions()))
        self.store.validate(state)

    def test_shared_findings_need_user_handling_and_remain_after_confirmation(self):
        self.service.register("sources", {"id": "other", "origin": "repository", "path": "spec.md", "kind": "markdown", "role": "contract", "scope": "example"}, approval="Add second source")
        self.service.register("links", {"id": "other-link", "test_id": "a", "source_id": "other", "nature": "behavior", "rationale": "Same requirement", "status": "established"}, approval="Established")
        review = self.finish()
        preview = self.service.removal_preview("spec")
        with self.assertRaises(Conflict):
            self.service.remove_source("spec", token=preview["confirmation_token"])
        self.service.remove_source("spec", token=preview["confirmation_token"], shared_handling="User requests preserving shared finding and detaching the removed source")
        retained = self.store.load()["reviews"][review["id"]]
        self.assertEqual(retained["source_ids"], ["other"])
        self.assertTrue(retained["invalidated"])
        self.assertNotIn("link-a", retained["evidence_versions"])
        self.assertEqual(self.run_for()["items"]["a"]["status"], "pending")

    def test_review_records_exact_artifact_identity_without_invalidating_other_sections(self):
        review = self.finish()
        artifact_hash = digest((self.root / "spec.md").read_bytes())
        self.assertEqual(review["evidence_versions"]["link-a"]["artifact_hash"], artifact_hash)
        with (self.root / "spec.md").open("a", encoding="utf-8") as stream:
            stream.write("\n## Other\nUnrelated\n")
        self.assertEqual(self.run_for()["items"]["a"]["status"], "reused")
        self.assertEqual(self.store.load()["reviews"][review["id"]]["evidence_versions"]["link-a"]["artifact_hash"], artifact_hash)

    def test_answering_dependent_question_prompts_new_review(self):
        self.service.record_question("q", "Applicable intent?", ["a"])
        self.finish(outcome="ambiguous", questions=["q"])
        self.assertEqual(self.run_for()["items"]["a"]["status"], "reused")
        self.service.answer("q", "Use strict behavior", "User clarified intent")
        self.assertEqual(self.run_for()["items"]["a"]["status"], "pending")

    def test_report_keeps_reviewed_reused_and_missing_separate(self):
        self.finish()
        run = self.service.start(SCOPE)
        self.finish(run, "b", outcome="contradiction")
        report = self.service.report(run["id"])
        self.assertEqual(report["reviewed"], ["b"])
        self.assertEqual(report["reused"], ["a"])
        self.assertEqual(len(report["discrepancies"]), 1)
        self.assertIn("Reviewed: 1; reused: 1", markdown_report(report))

    def test_large_inventory_output_is_paginated(self):
        def add(state):
            for index in range(1000):
                state["tests"][f"extra-{index}"] = {"id": f"extra-{index}", "path": "tests/test_example.py", "assertion": "Not linked"}
        self.store.update(add)
        result = compact(self.service.plan(SCOPE), 10, 0)
        self.assertEqual(result["total"], 1002)
        self.assertEqual(len(result["items"]), 10)
        self.assertEqual(result["summary"]["unlinked"], 1000)

    def test_cli_works_from_another_directory_with_spaces(self):
        command = [sys.executable, "-m", "truth_seeker", "--root", str(self.root), "--cache", str(self.cache.root), "--cache-only", "start", "--test", "a"]
        result = subprocess.run(command, cwd=self.base, text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = json.loads(result.stdout)
        self.assertEqual(run["summary"], {"pending": 1})
        self.assertNotIn("basis", run["items"]["a"])

    def test_line_ending_changes_reuse_text_but_preserve_reviewed_artifact_hashes(self):
        review = self.finish()
        hashes = {}
        for path in (self.test_path, self.root / "spec.md"):
            original = path.read_bytes()
            lf = original.replace(b"\r\n", b"\n")
            replacement = lf if b"\r\n" in original else lf.replace(b"\n", b"\r\n")
            self.assertNotEqual(digest(original), digest(replacement))
            hashes[path.name] = digest(original)
            path.write_bytes(replacement)
        self.assertEqual(self.run_for()["items"]["a"]["status"], "reused")
        saved = self.store.load()["reviews"][review["id"]]["evidence_versions"]
        self.assertEqual(saved["test"]["artifact_hash"], hashes[self.test_path.name])
        self.assertEqual(saved["link-a"]["artifact_hash"], hashes["spec.md"])

    def test_cli_output_is_utf8_even_with_an_ascii_pipe(self):
        assertion = "验证 café — 合同"
        self.store.update(lambda state: state["tests"]["a"].update(assertion=assertion))
        command = [sys.executable, "-m", "truth_seeker", "--root", str(self.root)]
        environment = {**os.environ, "PYTHONIOENCODING": "ascii"}
        result = subprocess.run([*command, "show", "tests", "a"], cwd=self.base,
                                env=environment, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["assertion"], assertion)
        missing = self.base / "不存在.json"
        result = subprocess.run([*command, "register", "tests", str(missing)], cwd=self.base,
                                env=environment, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(missing.name, json.loads(result.stderr.decode("utf-8"))["error"])

    def test_cli_directory_scope_accepts_native_separators_and_records_portable_paths(self):
        nested = self.root / "tests" / "nested"
        nested.mkdir()
        (nested / "case.py").write_bytes(b"assert True\n")
        self.service.register("tests", {"id": "nested", "path": "tests/nested/case.py", "assertion": "Nested test"})
        command = [sys.executable, "-m", "truth_seeker", "--root", str(self.root),
                   "start", "--directory", os.path.join("tests", "nested")]
        result = subprocess.run(command, cwd=self.base, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = json.loads(result.stdout)
        self.assertEqual(run["scope"], {"type": "directory", "value": "tests/nested"})
        self.assertEqual(set(run["items"]), {"nested"})

    def test_path_traversal_is_rejected_on_every_platform(self):
        for path in ("../outside.py", "C:/outside.py", "tests\\test_example.py", "/tmp/outside"):
            with self.subTest(path=path), self.assertRaises(TruthSeekerError):
                self.service.register("tests", {"id": "escape", "path": path, "assertion": "invalid"})


if __name__ == "__main__":
    unittest.main()
