"""Review orchestration data and explicit lifecycle operations, without AI judgment."""
import copy
import uuid

from .errors import Conflict, TruthSeekerError
from .evidence import Evidence
from .util import confined, digest, now


def identifier(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


class Service:
    def __init__(self, store, cache):
        self.store = store
        self.cache = cache
        self.evidence = Evidence(store, cache)

    def register(self, collection, record, *, approval=None, expected=None):
        if collection not in ("sources", "tests", "links", "decisions"):
            raise TruthSeekerError("Use lifecycle operations to record reviews, questions and actions")
        record = copy.deepcopy(record)
        if collection == "sources":
            if not approval:
                raise TruthSeekerError("Source establishment requires explicit user instruction")
            record["approval"] = approval
        if collection == "links":
            record.setdefault("status", "proposed")
            if record["status"] == "established":
                if not approval:
                    raise TruthSeekerError("Record the interview or user instruction establishing this relationship")
                record["approval"] = approval
        if collection == "decisions" and record.get("status") != "proposed":
            raise TruthSeekerError("Create proposed decisions, then explicitly accept them")
        def operation(state):
            key = record["id"]
            if key in state[collection]:
                raise Conflict("ID already exists; use an explicit lifecycle operation")
            state[collection][key] = record
            return record
        return self.store.update(operation, expected)

    def establish_link(self, link_id, approval):
        if not approval:
            raise TruthSeekerError("User instruction or interview rationale is required")
        def operation(state):
            state["links"][link_id].update(status="established", approval=approval)
            return state["links"][link_id]
        return self.store.update(operation)

    def accept_decision(self, decision_id, approval):
        if not approval:
            raise TruthSeekerError("User approval is required")
        def operation(state):
            decision = state["decisions"][decision_id]
            if decision["status"] != "proposed":
                raise Conflict("Only proposed decisions can be accepted; use supersede to change an accepted decision")
            decision.update(status="accepted", approval=approval, changed_at=now())
            return decision
        return self.store.update(operation)

    def supersede(self, old_id, replacement, approval):
        if not approval:
            raise TruthSeekerError("Replacing an accepted decision requires user approval")
        def operation(state):
            old = state["decisions"][old_id]
            if old["status"] != "accepted" or replacement["id"] in state["decisions"]:
                raise Conflict("Need an accepted predecessor and a new replacement ID")
            new = copy.deepcopy(replacement)
            new.update(status="accepted", approval=approval, supersedes=old_id, changed_at=now())
            old.update(status="superseded", superseded_by=new["id"])
            state["decisions"][new["id"]] = new
            return new
        return self.store.update(operation)

    def scope_ids(self, state, scope):
        if set(scope) != {"type", "value"}:
            raise TruthSeekerError("Scope requires type and value")
        kind, value = scope["type"], scope["value"]
        if kind == "repository":
            return sorted(state["tests"])
        if kind in ("test", "group"):
            ids = [value] if kind == "test" else value
            if not isinstance(ids, list) or not ids or any(k not in state["tests"] for k in ids):
                raise TruthSeekerError("Scope includes unknown tests or an empty group")
            return sorted(set(ids))
        if kind == "directory":
            directory = confined(self.store.root, value)
            return sorted(k for k, test in state["tests"].items()
                          if confined(self.store.root, test["path"]).is_relative_to(directory))
        raise TruthSeekerError("Scope type must be test, group, directory or repository")

    def select(self, state, scope, fresh=False):
        items = {}
        for test_id in self.scope_ids(state, scope):
            basis, missing, _ = self.evidence.snapshot(state, test_id)
            if not basis["links"]:
                items[test_id] = {"status": "unlinked", "reason": "No established relationship; no gap inferred", "basis": basis}
                continue
            if missing:
                items[test_id] = {"status": "blocked", "reason": "Required evidence unavailable", "basis": basis, "missing": missing}
                continue
            reviews = [review for review in state["reviews"].values()
                       if review["test_id"] == test_id and not review.get("invalidated")
                       and review["basis"] == basis]
            if reviews and not fresh:
                last = max(reviews, key=lambda r: r["completed_at"])
                items[test_id] = {"status": "reused", "reason": "Examined inputs unchanged", "basis": basis, "review_id": last["id"]}
            else:
                items[test_id] = {"status": "pending", "reason": "Fresh review requested" if fresh else "New or changed review inputs", "basis": basis}
        return items

    def plan(self, scope, fresh=False):
        state = self.store.load()
        return {"generation": state["generation"], "scope": scope, "fresh": fresh,
                "items": self.select(state, scope, fresh)}

    def start(self, scope, fresh=False):
        def operation(state):
            run = {"id": identifier("run"), "created_at": now(), "scope": scope,
                   "fresh": fresh, "items": self.select(state, scope, fresh)}
            state["runs"][run["id"]] = run
            return run
        return self.store.update(operation)

    def packet(self, run_id, test_id):
        state = self.store.load()
        item = state["runs"][run_id]["items"].get(test_id)
        if item is None:
            raise TruthSeekerError("Test is outside this run's requested scope")
        basis, missing, texts = self.evidence.snapshot(state, test_id, with_text=True)
        if basis != item["basis"]:
            raise Conflict("Inputs changed since run started; start a new scoped run")
        return {"run_id": run_id, "test_id": test_id, "basis_hash": digest({"basis": basis, "artifacts": {k: v["artifact_hash"] for k, v in texts.items()}}),
                "basis": basis, "missing": missing, "evidence": texts,
                "decisions": basis["decisions"],
                "questions": self.questions(state, test_id=test_id, source_ids={v["source_id"] for v in basis["links"].values()})}

    def complete(self, run_id, test_id, *, basis_hash, outcome, reasoning, claim,
                 limitations="", decision_ids=(), question_ids=()):
        def operation(state):
            item = state["runs"][run_id]["items"].get(test_id)
            if item is None or item["status"] not in ("pending", "blocked"):
                raise Conflict("Only unfinished in-scope work can be recorded")
            basis, missing, texts = self.evidence.snapshot(state, test_id, with_text=True)
            token = digest({"basis": basis, "artifacts": {k: v["artifact_hash"] for k, v in texts.items()}})
            if token != basis_hash or basis != item["basis"]:
                raise Conflict("Evidence changed after inspection; start a new scoped run")
            if missing and outcome != "insufficient-evidence":
                raise TruthSeekerError("Unavailable evidence cannot support a completed alignment conclusion")
            for key in decision_ids:
                if key not in basis["decisions"]:
                    raise TruthSeekerError("Decision is not applicable to this review")
            if outcome == "supported" and any(state["questions"][key]["status"] == "unresolved" for key in question_ids):
                raise TruthSeekerError("An unresolved dependent question cannot yield settled support")
            review = {"id": identifier("review"), "run_id": run_id, "test_id": test_id,
                      "basis": basis, "outcome": outcome, "reasoning": reasoning, "claim": claim,
                      "limitations": limitations, "decision_ids": list(decision_ids),
                      "question_ids": list(question_ids), "source_ids": sorted({v["source_id"] for v in basis["links"].values()}),
                      "evidence_versions": {k: {"artifact_hash": v["artifact_hash"], "content_hash": v["content_hash"],
                                                 "extractor": v["extractor"], "parser": v["parser"], "selector": v["selector"]}
                                            for k, v in texts.items()},
                      "completed_at": now()}
            state["reviews"][review["id"]] = review
            item.update(status="blocked" if missing else "completed", review_id=review["id"])
            return review
        return self.store.update(operation)

    def record_question(self, question_id, text, test_ids=(), source_ids=()):
        def operation(state):
            if question_id in state["questions"]:
                raise Conflict("Question already recorded; use questions to inspect eligibility")
            basis = self.evidence.question_basis(state, test_ids, source_ids)
            question = {"id": question_id, "text": text, "test_ids": list(test_ids),
                        "source_ids": list(source_ids), "status": "unresolved", "basis": basis,
                        "last_asked_basis": basis}
            state["questions"][question_id] = question
            return question
        return self.store.update(operation)

    def questions(self, state=None, *, test_id=None, source_ids=(), requested=False):
        state = state or self.store.load()
        result = []
        for question in state["questions"].values():
            if question["status"] != "unresolved":
                continue
            if test_id is not None and not (test_id in question["test_ids"] or (not question["test_ids"] and set(source_ids).intersection(question["source_ids"]))):
                continue
            current = self.evidence.question_basis(state, question["test_ids"], question["source_ids"])
            result.append({**question, "ask_again": requested or "last_asked_basis" not in question or current != question["last_asked_basis"]})
        return result

    def mark_asked(self, question_id, requested=False):
        def operation(state):
            question = state["questions"][question_id]
            basis = self.evidence.question_basis(state, question["test_ids"], question["source_ids"])
            if question["status"] != "unresolved" or (not requested and "last_asked_basis" in question and basis == question["last_asked_basis"]):
                raise Conflict("No relevant change or explicit request; do not repeat this question")
            question["last_asked_basis"] = basis
            return question
        return self.store.update(operation)

    def answer(self, question_id, answer, approval):
        if not approval:
            raise TruthSeekerError("Record the user's answer, not an AI substitute")
        def operation(state):
            question = state["questions"][question_id]
            question.update(status="answered", answer=answer, approval=approval)
            return question
        return self.store.update(operation)

    def todo(self, review_id, discrepancy):
        def operation(state):
            review = state["reviews"][review_id]
            if any(state["decisions"][d]["status"] == "accepted" for d in review["decision_ids"]):
                raise Conflict("Applicable decision already addresses this discrepancy; do not create an action")
            for todo in state["todos"].values():
                if todo["test_id"] == review["test_id"] and todo["discrepancy"] == discrepancy:
                    return todo  # Never reopen merely on rediscovery.
            todo = {"id": identifier("todo"), "test_id": review["test_id"], "review_id": review_id,
                    "discrepancy": discrepancy, "status": "open", "decision_ids": review["decision_ids"]}
            state["todos"][todo["id"]] = todo
            return todo
        return self.store.update(operation)

    def close_todo(self, todo_id, review_id, reason):
        def operation(state):
            todo, review = state["todos"][todo_id], state["reviews"][review_id]
            original = state["reviews"][todo["review_id"]]
            current, missing, _ = self.evidence.snapshot(state, review["test_id"])
            if (review["outcome"] != "supported" or review["test_id"] != todo["test_id"]
                    or review["claim"] != original["claim"] or review["completed_at"] <= original["completed_at"]
                    or missing or review.get("invalidated") or review["basis"] != current):
                raise TruthSeekerError("Closure needs a current later review supporting the same test and claim")
            if set(original["source_ids"]) != set(review["source_ids"]):
                raise TruthSeekerError("Changed source coverage needs clarification before closing this to-do")
            todo.update(status="closed", closed_by=review_id, closure_reason=reason)
            return todo
        return self.store.update(operation)

    def relocate(self, collection, key, location, approval=None):
        if collection not in ("sources", "tests"):
            raise TruthSeekerError("Only source or test locations can be changed")
        if not approval:
            raise TruthSeekerError("Establish identity with the user before transferring history")
        def operation(state):
            record = state[collection][key]
            field = "url" if record.get("origin") == "external" else "path"
            record[field] = location
            return record
        return self.store.update(operation)

    def import_source(self, source_id, path, *, expected_hash=None, adopt=False, version=None):
        state = self.store.load()
        source = state["sources"][source_id]
        if source["origin"] != "external":
            raise TruthSeekerError("Cache import requires an established external source")
        with open(path, "rb") as stream:
            metadata = self.cache.import_bytes(source["url"], stream.read(64 * 1024 * 1024 + 1),
                                               expected_hash=expected_hash, version=version)
        return self.adopt_observation(source_id, metadata, adopt, state["generation"])

    def fetch_source(self, source_id, *, allow_network=False, adopt=False):
        state = self.store.load()
        source = state["sources"][source_id]
        if source["origin"] != "external":
            raise TruthSeekerError("Acquisition requires an established external source")
        metadata = self.cache.acquire(source["url"], cache_only=not allow_network, version=source.get("edition"))
        return self.adopt_observation(source_id, metadata, adopt, state["generation"])

    def adopt_observation(self, source_id, metadata, adopt, generation):
        def operation(state):
            source = state["sources"][source_id]
            source["observed"] = metadata
            if adopt or "object_hash" not in source:
                source["object_hash"] = metadata["object_hash"]
            return source
        return self.store.update(operation, generation)

    def removal_preview(self, source_id, state=None):
        state = state or self.store.load()
        if source_id not in state["sources"]:
            raise TruthSeekerError("Unknown source")
        affected = sorted(k for k, d in state["decisions"].items() if source_id in d["source_ids"])
        last = [k for k in affected if set(state["decisions"][k]["source_ids"]) == {source_id}]
        referenced_reviews = {t["review_id"] for t in state["todos"].values()} | {t["closed_by"] for t in state["todos"].values() if "closed_by" in t}
        shared = sorted(k for k, r in state["reviews"].items() if source_id in r["source_ids"]
                        and (len(r["source_ids"]) > 1 or k in referenced_reviews))
        impact = {"source_id": source_id, "generation": state["generation"], "affected_decisions": affected,
                  "decisions_losing_last_source": last, "count": len(last), "shared_findings": shared}
        return {**impact, "confirmation_token": digest(impact),
                "consequence": "Decisions are preserved; ask user how to handle those left without sources"}

    def remove_source(self, source_id, *, token, confirmation=None, shared_handling=None):
        def operation(state):
            preview = self.removal_preview(source_id, state)
            if token != preview["confirmation_token"]:
                raise Conflict("Removal impact changed; preview and confirm the current impact")
            if preview["count"] and not confirmation:
                raise Conflict("User confirmation required before removing the last source for decisions")
            if preview["shared_findings"] and not shared_handling:
                raise Conflict("Shared findings need explicit user handling instructions before source removal")
            link_ids = {k for k, link in state["links"].items() if link["source_id"] == source_id}
            affected_tests = {state["links"][key]["test_id"] for key in link_ids}
            del state["sources"][source_id]
            for key in link_ids:
                del state["links"][key]
            for decision in state["decisions"].values():
                if source_id in decision["source_ids"]:
                    decision["source_ids"].remove(source_id)
            # Remove obsolete evidence locators, not the decisions or shared conclusions themselves.
            def detach_basis(basis):
                for key in link_ids:
                    basis.get("sources", {}).pop(key, None)
                    basis.get("links", {}).pop(key, None)
                for value in basis.get("decisions", {}).values():
                    if source_id in value.get("source_ids", []):
                        value["source_ids"].remove(source_id)
            removed_reviews = {key for key, review in state["reviews"].items()
                               if review["source_ids"] == [source_id] and key not in preview["shared_findings"]}
            for key in removed_reviews:
                del state["reviews"][key]
            for review in state["reviews"].values():
                if source_id in review["source_ids"]:
                    review["source_ids"].remove(source_id)
                    detach_basis(review["basis"])
                    for key in link_ids:
                        review["evidence_versions"].pop(key, None)
                    review["invalidated"] = True
            for run in state["runs"].values():
                for item in run["items"].values():
                    if item.get("review_id") in removed_reviews:
                        del item["review_id"]
                    if any(link["source_id"] == source_id for link in item["basis"].get("links", {}).values()):
                        detach_basis(item["basis"])
                        item.update(status="pending", reason="Source explicitly removed; prior review no longer reusable")
            for question in state["questions"].values():
                affected = source_id in question["source_ids"] or affected_tests.intersection(question["test_ids"])
                if source_id in question["source_ids"]:
                    question["source_ids"].remove(source_id)
                if affected:
                    # Discard removed-source history, but do not mark a changed question as asked.
                    question["basis"] = self.evidence.question_basis(state, question["test_ids"], question["source_ids"])
                    question.pop("last_asked_basis", None)
            for decision_id in preview["decisions_losing_last_source"]:
                question_id = identifier("question")
                decision = state["decisions"][decision_id]
                state["questions"][question_id] = {
                    "id": question_id, "text": f"Decision {decision_id} has no remaining sources after confirmed removal. How should it be handled?",
                    "test_ids": decision["test_ids"], "source_ids": [], "status": "unresolved",
                    "basis": self.evidence.question_basis(state, decision["test_ids"], [])}
            return {"removed": source_id, "decisions_preserved": preview["affected_decisions"],
                    "unresolved_decisions": preview["decisions_losing_last_source"], "shared_handling": shared_handling}
        return self.store.update(operation)

    def report(self, run_id):
        state = self.store.load()
        run = state["runs"][run_id]
        result = {"run_id": run_id, "scope": run["scope"], "reviewed": [], "reused": [],
                  "unavailable": [], "unfinished": [], "discrepancies": [], "questions": [], "actions": []}
        selected = set(run["items"])
        source_ids = set()
        for test_id, item in run["items"].items():
            source_ids.update(link["source_id"] for link in item["basis"].get("links", {}).values())
            status = item["status"]
            if status in ("completed", "reused"):
                result["reviewed" if status == "completed" else "reused"].append(test_id)
                review = state["reviews"][item["review_id"]]
                if review["outcome"] != "supported":
                    result["discrepancies"].append(review)
            elif status == "blocked":
                result["unavailable"].append({"test_id": test_id, "missing": item.get("missing", [])})
            elif status == "pending":
                result["unfinished"].append(test_id)
        result["questions"] = [q for q in self.questions(state)
                               if selected.intersection(q["test_ids"]) or (not q["test_ids"] and source_ids.intersection(q["source_ids"]))]
        result["actions"] = [t for t in state["todos"].values() if t["test_id"] in selected and t["status"] == "open"]
        return result
