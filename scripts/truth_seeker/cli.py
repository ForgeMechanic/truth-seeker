"""Source-distributed CLI. JSON in/out; no model calls and no implicit network."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .cache import Cache
from .errors import Conflict, TruthSeekerError
from .service import Service
from .store import Store, find_root
from .util import read_json


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, help="Consumer repository; otherwise search current directory and parents")
    result.add_argument("--cache", type=Path, help="External cache directory, outside the consumer repository")
    result.add_argument("--shared-cache", action="append", default=[], type=Path, help="Additional read-only cache root")
    result.add_argument("--cache-only", action="store_true", help="Prohibit all acquisition, including explicit fetch")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("validate")
    register = commands.add_parser("register", help="Record explicitly established sources or proposed relationships/decisions")
    register.add_argument("collection", choices=["sources", "tests", "links", "decisions"])
    register.add_argument("file", type=Path)
    register.add_argument("--approval", help="User instruction establishing the source/relationship")
    register.add_argument("--expected-generation", type=int)
    for name in ("plan", "start"):
        sub = commands.add_parser(name)
        group = sub.add_mutually_exclusive_group(required=True)
        group.add_argument("--test")
        group.add_argument("--tests", nargs="+")
        group.add_argument("--directory")
        group.add_argument("--repository", action="store_true")
        sub.add_argument("--fresh", action="store_true")
        sub.add_argument("--limit", type=int, default=50)
        sub.add_argument("--offset", type=int, default=0)
    packet = commands.add_parser("packet")
    packet.add_argument("run")
    packet.add_argument("test")
    complete = commands.add_parser("complete")
    complete.add_argument("run")
    complete.add_argument("test")
    complete.add_argument("file", type=Path, help="JSON: basis_hash, outcome, reasoning, claim, optional limitations/decision_ids/question_ids")
    for name in ("establish-link", "accept"):
        sub = commands.add_parser(name)
        sub.add_argument("id")
        sub.add_argument("--approval", required=True)
    supersede = commands.add_parser("supersede")
    supersede.add_argument("old")
    supersede.add_argument("file", type=Path)
    supersede.add_argument("--approval", required=True)
    question = commands.add_parser("question")
    question.add_argument("id")
    question.add_argument("text")
    question.add_argument("--tests", nargs="*", default=[])
    question.add_argument("--sources", nargs="*", default=[])
    questions = commands.add_parser("questions")
    questions.add_argument("--requested", action="store_true", help="Explicitly requested reconsideration")
    asked = commands.add_parser("mark-asked")
    asked.add_argument("id")
    asked.add_argument("--requested", action="store_true")
    answer = commands.add_parser("answer")
    answer.add_argument("id")
    answer.add_argument("text")
    answer.add_argument("--approval", required=True)
    todo = commands.add_parser("todo")
    todo.add_argument("review")
    todo.add_argument("discrepancy")
    close = commands.add_parser("close")
    close.add_argument("todo")
    close.add_argument("review")
    close.add_argument("reason")
    relocate = commands.add_parser("relocate")
    relocate.add_argument("collection", choices=["sources", "tests"])
    relocate.add_argument("id")
    relocate.add_argument("location")
    relocate.add_argument("--approval", required=True)
    imported = commands.add_parser("import")
    imported.add_argument("source")
    imported.add_argument("file", type=Path)
    imported.add_argument("--sha256")
    imported.add_argument("--adopt", action="store_true", help="Select imported version if a version is already selected")
    imported.add_argument("--version")
    fetched = commands.add_parser("fetch")
    fetched.add_argument("source")
    fetched.add_argument("--allow-network", action="store_true", help="Explicit acquisition authorization; never inferred from review")
    fetched.add_argument("--adopt", action="store_true")
    preview = commands.add_parser("remove-preview")
    preview.add_argument("source")
    removal = commands.add_parser("remove")
    removal.add_argument("source")
    removal.add_argument("--token", required=True)
    removal.add_argument("--confirmation", help="User's confirmation after seeing decisions losing their last source")
    removal.add_argument("--shared-handling", help="User instruction to preserve shared findings and detach removed evidence")
    report = commands.add_parser("report")
    report.add_argument("run")
    report.add_argument("--markdown", action="store_true")
    show = commands.add_parser("show")
    show.add_argument("collection", choices=["sources", "tests", "links", "decisions", "questions", "reviews", "todos", "runs"])
    show.add_argument("id", nargs="?")
    show.add_argument("--limit", type=int, default=50)
    show.add_argument("--offset", type=int, default=0)
    extraction = commands.add_parser("extract")
    extraction.add_argument("source")
    extraction.add_argument("--selector", type=Path, help="JSON selector file")
    return result


def compact(selection, limit, offset):
    if limit < 1 or offset < 0:
        raise TruthSeekerError("Limit must be positive and offset nonnegative")
    items = list(selection["items"].items())
    return {**{k: v for k, v in selection.items() if k != "items"},
            "summary": dict(Counter(item["status"] for _, item in items)),
            "total": len(items), "offset": offset,
            "items": {k: {field: value for field, value in item.items() if field != "basis"}
                      for k, item in items[offset:offset + limit]}}


def markdown_report(report):
    lines = ["# Truth Seeker review", "", f"Run: `{report['run_id']}`", "",
             f"Reviewed: {len(report['reviewed'])}; reused: {len(report['reused'])}; "
             f"unavailable: {len(report['unavailable'])}; unfinished: {len(report['unfinished'])}."]
    for title, key in (("Discrepancies", "discrepancies"), ("Unresolved questions", "questions"),
                       ("Action items", "actions"), ("Missing evidence", "unavailable")):
        lines.extend(["", f"## {title}", ""])
        for item in report[key]:
            if key == "discrepancies":
                decisions = item["decision_ids"]
                suffix = f" Recorded decisions: {', '.join(decisions)}." if decisions else ""
                lines.append(f"- {item['test_id']}: {item['outcome']} — {item['reasoning']}{suffix}")
            elif key == "questions":
                lines.append(f"- {item['id']}: {item['text']} (ask again: {item['ask_again']})")
            elif key == "actions":
                lines.append(f"- {item['id']}: {item['discrepancy']}")
            else:
                lines.append(f"- {item['test_id']}: {'; '.join(item['missing'])}")
        if not report[key]:
            lines.append("None recorded.")
    return "\n".join(lines)


def execute(args):
    root = args.root or (Path.cwd() if args.command == "init" else find_root(Path.cwd()))
    if args.command == "init":
        store = Store.initialize(root)
        return {"initialized": str(store.directory), "generation": 0}
    store = Store(root)
    cache = Cache(root, args.cache, args.shared_cache)
    service = Service(store, cache)
    command = args.command
    if command == "validate":
        state = store.load()
        return {"valid": True, "generation": state["generation"]}
    if command == "register":
        return service.register(args.collection, read_json(args.file), approval=args.approval, expected=args.expected_generation)
    if command in ("plan", "start"):
        scope = {"type": "test", "value": args.test} if args.test else (
            {"type": "group", "value": args.tests} if args.tests else (
                {"type": "directory", "value": args.directory} if args.directory is not None else {"type": "repository", "value": "."}))
        return compact(getattr(service, command)(scope, args.fresh), args.limit, args.offset)
    if command == "packet":
        return service.packet(args.run, args.test)
    if command == "complete":
        return service.complete(args.run, args.test, **read_json(args.file))
    if command == "establish-link":
        return service.establish_link(args.id, args.approval)
    if command == "accept":
        return service.accept_decision(args.id, args.approval)
    if command == "supersede":
        return service.supersede(args.old, read_json(args.file), args.approval)
    if command == "question":
        return service.record_question(args.id, args.text, args.tests, args.sources)
    if command == "questions":
        return service.questions(requested=args.requested)
    if command == "mark-asked":
        return service.mark_asked(args.id, args.requested)
    if command == "answer":
        return service.answer(args.id, args.text, args.approval)
    if command == "todo":
        return service.todo(args.review, args.discrepancy)
    if command == "close":
        return service.close_todo(args.todo, args.review, args.reason)
    if command == "relocate":
        return service.relocate(args.collection, args.id, args.location, args.approval)
    if command == "import":
        return service.import_source(args.source, args.file, expected_hash=args.sha256, adopt=args.adopt, version=args.version)
    if command == "fetch":
        if args.cache_only and args.allow_network:
            raise TruthSeekerError("--cache-only cannot be combined with --allow-network")
        return service.fetch_source(args.source, allow_network=args.allow_network, adopt=args.adopt)
    if command == "remove-preview":
        return service.removal_preview(args.source)
    if command == "remove":
        return service.remove_source(args.source, token=args.token, confirmation=args.confirmation, shared_handling=args.shared_handling)
    if command == "report":
        report = service.report(args.run)
        return markdown_report(report) if args.markdown else report
    if command == "show":
        records = store.load()[args.collection]
        if args.id:
            return records[args.id]
        if args.limit < 1 or args.offset < 0:
            raise TruthSeekerError("Limit must be positive and offset nonnegative")
        return {"total": len(records), "records": dict(list(records.items())[args.offset:args.offset + args.limit])}
    if command == "extract":
        source = store.load()["sources"][args.source]
        return service.evidence.source(source, read_json(args.selector) if args.selector else None)
    raise TruthSeekerError("Unknown operation")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (TruthSeekerError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "kind": type(exc).__name__}), file=sys.stderr)
        return 3 if isinstance(exc, Conflict) else 2


if __name__ == "__main__":
    sys.exit(main())
