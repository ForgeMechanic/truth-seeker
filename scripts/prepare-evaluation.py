"""Prepare, but never answer, the realistic skill evaluation fixture in a temporary repository."""
import argparse
import shutil
from pathlib import Path

from truth_seeker.cache import Cache
from truth_seeker.service import Service
from truth_seeker.store import Store
from truth_seeker.util import read_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
args = parser.parse_args()
fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/alignment"
if args.directory.exists():
    parser.error("Choose a new evaluation directory")
shutil.copytree(fixture, args.directory)
store = Store.initialize(args.directory)
service = Service(store, Cache(args.directory, args.directory.parent / "evaluation-cache"))
records = read_json(args.directory / "records.json")
for collection in ("sources", "tests", "links"):
    for record in records[collection]:
        service.register(collection, record, approval="Established by the fixture's evaluation request")
service.register("decisions", records["decision"])
service.accept_decision(records["decision"]["id"], "Existing accepted exception in evaluation request")
print(f"Prepared {args.directory}; read request.md, then use the skill to review. No conclusions generated.")
