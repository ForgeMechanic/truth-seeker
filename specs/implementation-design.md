# Truth Seeker implementation choices

This source implementation follows [the requirements](truth-seeker-spec.md) and
[implementation plan](truth-seeker-implementation-plan.md). These are implementation
choices, not retroactive changes to the user requirements.

## Skill and execution

The repository root is the portable `truth-seeker` skill. `SKILL.md` routes to focused
references. `scripts/truth-seeker.py` supports direct source invocation; the optional
Python package installs `truth-seeker` and `python -m truth_seeker`. Installing the
Python package alone does not register the skill with an agent. No model API client,
API credential, agent-specific UI metadata, or compiled project binary is required.

Python 3.11+ is supported. JSON validation uses `jsonschema` 4.x and PDF extraction
uses `pypdf` 5.x/6.x. HTML uses the standard library parser; Word `.docx` uses ZIP and
XML parsing. Dependency licenses and source can be inspected through those packages;
third-party dependency distributions are separate from this project's source-only
helpers. `pyproject.toml` declares supported ranges; CI tests the resolved environment.

## Persistent format

Format 1 uses `.truth-seeker/manifest.json`, `knowledge.json`, local JSON Schemas,
and `AGENTS.md`. A manifest identifies the data and schema without internet access.
The authoritative schemas are in `schemas/`; packaged copies and the consumer
instructions in `scripts/truth_seeker/data/` are checked against their source templates
by `scripts/validate-skill.py`.

Collections are sources, tests, links, reviews, decisions, questions, to-dos, and runs.
Each uses stable string IDs. Proposed versus established relationships and proposed
versus accepted decisions are explicit. An answer does not implicitly accept a policy.
Additional core fields are rejected; `extensions` permits project metadata.

One authoritative JSON snapshot makes related transitions atomic. A writer creates a
lock directory, reloads state, applies a transition, validates the whole result,
increments `generation`, and replaces the file atomically after flushing it. Failed
validation or replacement leaves the previous snapshot. Concurrent writers and
stale generation/removal-impact tokens fail rather than silently overwrite records.
A killed writer may leave a lock requiring inspection and manual removal. There is
no guarantee of preserving reasoning that was never recorded. Schemas reject unknown
versions; migrations are not silently inferred.

User-edited records remain possible and must be validated. Approval text records
actual user instruction; it cannot authenticate a human or sandbox an agent. Skill
instructions govern when lifecycle operations may be called.

## Evidence identity and reuse

SHA-256 identifies raw artifact bytes and selected extracted text. Review records
retain both identities, extraction selector and extractor identity. Selection compares
only relevant selected content, source applicability, recorded links, decisions and
question status, so unrelated document sections can change without reopening a
section-specific review. Raw artifact hashes remain in review provenance rather than
forcing every section review stale. Packet tokens bind both the selected basis and
the exact artifacts, preventing completion after evidence changed during inspection.

Helpers read working-tree bytes, including staged/unstaged/untracked registered
files; they do not infer chronological ordering from commit dates or invoke Git.
Logical test identity is distinct from content identity. Python tests can use qualified
AST symbols; other languages can use explicit file or line ranges. Pure location
changes require established identity. Changed test content still causes review.

Markdown selectors support ATX heading paths. HTML heading names/IDs, standard Word
heading styles and PDF page/bookmark locators are deterministic within supported
formats. Unresolvable or ambiguous sections become unavailable, never guessed or
silently widened. Semantic cross-section dependencies must be explicitly recorded;
no inferred dependency graph is claimed.

## Cache and acquisition

Primary and read-only shared caches must be outside the consumer repository. Objects
are stored under `objects/SHA256`; `origins/` maps URL hashes to latest observations,
and `metadata/URL_HASH/SHA256.json` retains per-artifact provenance. The consumer source
selects an `object_hash` independently of its latest `observed` metadata. Reads verify
hashes. Old versions are retained; no automatic eviction or garbage collection is
implemented. Missing provenance remains unknown. Root paths stay out of committed
records.

Initial import/fetch selects the first artifact. Subsequent observations do not change
the selected version without `--adopt`. Review code never calls acquisition. Explicit
fetch supports HTTP/HTTPS with conditional validators and local file URLs. It has a
30-second timeout and 64 MiB artifact limit. No authenticated-login integration is
implemented; manually supplied files cover those sources. Cache-only checks happen
before constructing a network client. Host-agent browsing restrictions additionally
come from the skill; these helpers cannot sandbox arbitrary host tools.

## Decisions and removal

Accepted decision replacement preserves the predecessor and rationale. Fixed to-dos
can close only against a current later review of the same test, claim and source
coverage. The agent must still assess whether it resolves the same discrepancy;
Python does not determine semantic equivalence from prose.

Source-removal impact is bound to the current generation. Removing one source
preserves decisions and remaining associations. Removing a last supporting source
requires impact confirmation, preserves decisions with empty `source_ids`, and records
an unresolved handling question. Empty source IDs do not imply rejection or acceptance
of any new meaning. Shared review/action records need an explicit user instruction
to preserve them while detaching removed evidence; otherwise removal is blocked.
Source-only review history is removed, while shared records retained by instruction
are invalidated for reuse. The external cache is not automatically pruned.

## Files and permissions

- Reads: explicitly registered repository files, local schema/JSON records, imported
  artifacts, and configured cache objects. Repository locators cannot escape the
  consumer root, including through symlinks; no consumer code or tests are executed.
- Writes: `.truth-seeker/` records, schemas and instructions during explicit init or
  maintenance; cache objects/metadata during explicit import or fetch. Reviewed tests,
  implementation and source documents are never rewritten by helpers.
- Network: only explicitly authorized fetch; none for review, extraction, planning,
  reports, validation or import. JSON Schema resolution is restricted to fragments.
- Subprocesses: none in shipped helper code. Tests use subprocesses to exercise the
  installed command and a localhost HTTP server to test acquisition.
- Installation: dependency resolution happens only through the user's explicit
  installation command. No review command downloads tools or installs packages.

The lifecycle boundary, cached-artifact provenance and host permissions still matter;
readable source and capability descriptions are not security sandboxes.
