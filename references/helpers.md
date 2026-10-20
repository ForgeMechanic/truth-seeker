# Python helper interface

Requires Python 3.11+ and the dependencies declared in `pyproject.toml`. Use the
installed `truth-seeker` command or `python /absolute/skill/scripts/truth-seeker.py`.
The latter needs dependencies in the selected interpreter but no package installation.
Do not automatically install dependencies during a consumer review.

Global options precede the operation:

```text
python HELPER --root CONSUMER --cache EXTERNAL_CACHE --cache-only OPERATION ...
```

`HELPER`, `CONSUMER`, `EXTERNAL_CACHE`, `RUN`, and `TEST` below are placeholders.
`--root` can be omitted after initialization: it searches the current directory and
parents. `init` without it initializes the current directory. IDs are explicit stable
strings. Recorded repository paths use forward slashes on all platforms and cannot
escape the repository. CLI `--directory` also accepts native OS separators, converting
them to the stored format. The helper never executes consumer tests or invokes Git.

Output is UTF-8 JSON except `report --markdown`, which is UTF-8 text. Redirected output
does not depend on the host's default code page. JSON input accepts UTF-8 with or
without a BOM. Exit status: 0 success, 2 invalid
input/unavailable operation, 3 stale state or an unmet confirmation prerequisite.
A successful plan/report can contain blocked work; exit 0 does not mean alignment.

## Initialize and establish records

```text
python HELPER --root CONSUMER init
python HELPER --root CONSUMER register sources source.json --approval "User selected this contract"
python HELPER --root CONSUMER register tests test.json
python HELPER --root CONSUMER register links link.json --approval "User established the association"
python HELPER --root CONSUMER validate
```

Minimal local `source.json`:

```json
{"id":"contract","origin":"repository","path":"docs/contract.md","kind":"markdown","role":"project requirements","scope":"Parser behavior"}
```

External source:

```json
{"id":"standard","origin":"external","url":"https://example.org/spec.pdf","kind":"pdf","role":"normative standard","scope":"Selected parser requirements","edition":"1"}
```

`test.json`:

```json
{"id":"reject-empty","path":"tests/test_parser.py","selector":{"python":"test_reject_empty"},"assertion":"Empty input is rejected"}
```

`link.json`:

```json
{"id":"empty-contract","test_id":"reject-empty","source_id":"contract","selector":{"heading":"Empty input"},"nature":"behavior","rationale":"User identified this contract section","status":"established"}
```

For a proposed link omit approval and use `status: proposed`, then `establish-link ID
--approval TEXT` after the interview. `nature: architecture` supports architectural
associations. Omit `selector` for a recorded whole-document relationship.

`register` never overwrites an existing ID. `--expected-generation N` can reject a
write based on stale inspection. Accepted decisions use dedicated operations.

## Plan and review

```text
python HELPER --root CONSUMER --cache-only plan --test TEST
python HELPER --root CONSUMER start --tests TEST OTHER_TEST
python HELPER --root CONSUMER start --directory tests/parser --fresh
python HELPER --root CONSUMER start --repository
python HELPER --root CONSUMER packet RUN TEST
python HELPER --root CONSUMER complete RUN TEST result.json
python HELPER --root CONSUMER report RUN --markdown
```

`plan` does not write. `start` saves selected work. Both accept `--limit` (default 50)
and `--offset`; compact output omits basis data. A scope is mandatory. `packet` reads
one selected item and returns evidence and `basis_hash`. `result.json` must contain
that returned token rather than a fabricated hash:

```json
{"basis_hash":"COPY_FROM_PACKET","outcome":"contradiction","claim":"Empty input is rejected","reasoning":"The test accepts empty input while the contract requires rejection.","limitations":"","decision_ids":[],"question_ids":[]}
```

Other outcomes: `supported`, `ambiguous`, `insufficient-evidence`. Reference applicable
decision IDs for known differences and question IDs for unsettled dependent results.
No source refresh or baseline mutation is hidden inside these operations.

## Interview and decisions

```text
python HELPER --root CONSUMER question q-empty "Is permissive empty-input handling intentional?" --tests TEST --sources contract
python HELPER --root CONSUMER questions
python HELPER --root CONSUMER mark-asked q-empty
python HELPER --root CONSUMER answer q-empty "Yes, for compatibility" --approval "User's answer"
python HELPER --root CONSUMER register decisions decision.json
python HELPER --root CONSUMER accept compatibility --approval "User accepted this difference"
python HELPER --root CONSUMER supersede compatibility replacement.json --approval "User approved changing this decision"
```

A proposed decision record:

```json
{"id":"compatibility","statement":"Allow empty input for compatibility","rationale":"Existing consumers rely on it","test_ids":["reject-empty"],"source_ids":["contract"],"status":"proposed"}
```

`questions --requested` means the user explicitly requested reconsideration. After
that question is actually raised, use `mark-asked ID --requested`. Do not treat a
flag as evidence of user intent. `answer` records a reply; acceptance is separate.

## Maintenance and inspection

```text
python HELPER --root CONSUMER todo REVIEW "Empty-input handling conflicts"
python HELPER --root CONSUMER close TODO LATER_REVIEW "The later review confirms the same claim now aligns"
python HELPER --root CONSUMER relocate tests TEST tests/moved.py --approval "User established same test identity"
python HELPER --root CONSUMER relocate sources contract docs/new-contract.md --approval "Same document moved"
python HELPER --root CONSUMER remove-preview contract
python HELPER --root CONSUMER remove contract --token TOKEN --confirmation "User confirmed the displayed impact"
python HELPER --root CONSUMER show decisions compatibility
python HELPER --root CONSUMER show reviews --limit 10 --offset 0
```

Removal may also require `--shared-handling` with the actual user's instruction to
preserve shared findings while detaching removed evidence. See the maintenance
reference before performing removal. `show` reads records and paginates collections.
No operation deletes accepted decisions.

## Direct JSON edits and recovery

Schemas are bundled with the consuming repository. A user or another agent may edit
records directly, but should validate afterward and preserve the documented lifecycle
rules. Tool flags and stored approval text cannot authenticate who made an edit.
Do not invent migrations for an unknown format: the helper rejects it explicitly.

Each operation locks and atomically replaces `knowledge.json`. Normal failures leave
the old snapshot intact. A process killed while holding the lock can leave
`.truth-seeker/.write-lock/owner`. Check whether that PID is live on the original
machine and whether another writer is active before manually removing the stale lock.
The helper never auto-deletes a lock based only on elapsed time. Unrecorded reasoning
may need repeating, but earlier committed review units remain available.
