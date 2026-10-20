"""Snapshot selected local evidence, never refresh it or discover relationships."""
from .documents import extract
from .errors import MissingEvidence
from .util import confined


class Evidence:
    def __init__(self, store, cache):
        self.store = store
        self.cache = cache

    def source(self, record, selector=None):
        try:
            if record["origin"] == "repository":
                data = confined(self.store.root, record["path"]).read_bytes()
            else:
                data = self.cache.read(record.get("object_hash"))
        except OSError as exc:
            raise MissingEvidence(f"Source unavailable: {record['id']}: {exc}") from exc
        return extract(data, record["kind"], selector)

    def test(self, record):
        try:
            data = confined(self.store.root, record["path"]).read_bytes()
        except OSError as exc:
            raise MissingEvidence(f"Test unavailable: {record['id']}: {exc}") from exc
        return extract(data, "text", record.get("selector"))

    def snapshot(self, state, test_id, *, with_text=False):
        test = state["tests"][test_id]
        links = {key: link for key, link in state["links"].items()
                 if link["test_id"] == test_id and link["status"] == "established"}
        source_ids = {link["source_id"] for link in links.values()}
        basis = {"test": {}, "sources": {}, "links": links, "decisions": {}, "questions": {}}
        texts, missing = {}, []
        try:
            artifact = self.test(test)
            basis["test"] = {"hash": artifact["content_hash"], "extractor": artifact["extractor"],
                             "assertion": test["assertion"], "selector": test.get("selector", {})}
            if with_text:
                texts["test"] = artifact
        except MissingEvidence as exc:
            missing.append(str(exc))
        for link_id, link in links.items():
            record = state["sources"][link["source_id"]]
            try:
                artifact = self.source(record, link.get("selector"))
                basis["sources"][link_id] = {
                    "source_id": record["id"], "hash": artifact["content_hash"],
                    "extractor": artifact["extractor"], "role": record["role"], "scope": record["scope"],
                    "edition": record.get("edition"), "kind": record["kind"]}
                if with_text:
                    texts[link_id] = artifact
            except MissingEvidence as exc:
                missing.append(f"{record['id']}: {exc}")
        for key, decision in state["decisions"].items():
            if (test_id in decision["test_ids"] or (not decision["test_ids"] and source_ids.intersection(decision["source_ids"]))):
                basis["decisions"][key] = decision
        for key, question in state["questions"].items():
            if test_id in question["test_ids"] or (not question["test_ids"] and source_ids.intersection(question["source_ids"])):
                basis["questions"][key] = {field: question[field] for field in
                                           ("text", "status", "answer") if field in question}
        return basis, missing, texts

    def question_basis(self, state, test_ids, source_ids):
        basis = {"tests": {}, "sources": {}}
        for test_id in test_ids:
            snap, missing, _ = self.snapshot(state, test_id)
            snap.pop("questions", None)  # Asking a question must not itself trigger re-asking.
            basis["tests"][test_id] = {"snapshot": snap, "missing": missing}
        for source_id in source_ids:
            record = state["sources"][source_id]
            try:
                content = self.source(record)
                value = {"hash": content["content_hash"], "role": record["role"],
                         "scope": record["scope"], "edition": record.get("edition")}
            except MissingEvidence as exc:
                value = {"unavailable": str(exc)}
            basis["sources"][source_id] = value
        # Decisions directly tied to a source may matter even when there are no test IDs.
        basis["decisions"] = {k: d for k, d in state["decisions"].items()
                              if set(source_ids).intersection(d["source_ids"])}
        return basis
