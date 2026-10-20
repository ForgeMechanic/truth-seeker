"""Portable structural check, not a substitute for behavioral evaluation."""
import re
from pathlib import Path

from jsonschema import Draft202012Validator
from truth_seeker.util import configure_output, normalize_newlines, read_json

configure_output()
root = Path(__file__).resolve().parents[1]
text = (root / "SKILL.md").read_text(encoding="utf-8")
assert text.startswith("---\n"), "Missing skill frontmatter"
frontmatter = text.split("---", 2)[1]
assert re.search(r"^name: truth-seeker$", frontmatter, re.M)
assert re.search(r"^description: .+", frontmatter, re.M)
for document in [root / "SKILL.md", root / "README.md", *sorted((root / "references").glob("*.md")), *sorted((root / "specs").glob("*.md"))]:
    for destination in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        if "://" not in destination and not destination.startswith("#"):
            assert (document.parent / destination.split("#")[0]).exists(), f"Broken link: {destination}"
for path in (root / "schemas").glob("*.json"):
    schema = read_json(path)
    Draft202012Validator.check_schema(schema)
    assert schema == read_json(root / "scripts/truth_seeker/data" / path.name), "Bundled schema drift"
assert normalize_newlines((root / "templates/AGENTS.md").read_text(encoding="utf-8-sig")) == normalize_newlines(
    (root / "scripts/truth_seeker/data/AGENTS.md").read_text(encoding="utf-8-sig")), "Bundled instructions drift"
assert (root / "LICENSE").is_file()
print("Skill structure, references, local schemas and bundled resources are valid.")
