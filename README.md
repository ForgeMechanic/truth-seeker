# Truth Seeker

Truth Seeker is an Agent Skill that adversarially reviews existing unit tests against your established specifications and architectural documents. It asks whether the tests agree with the requirements your project has chosen to follow, preserves evidence and decisions, and avoids repeating unchanged reviews.

A discrepancy is something to investigate, not automatic proof that a test is wrong. Documentation may be outdated, a test may encode a mistaken assumption, or a difference may be intentional. The agent asks you when a judgment call is needed and remembers your answer.

**Status:** Initial source implementation. The portable skill and Python helpers are available in this checkout. Local tests and evaluation evidence are described in [validation](specs/implementation-validation.md); the Windows/macOS CI matrix must run before portability is considered verified on those platforms. This is not a standalone AI service: your agent performs the reasoning and interview.

## Install from source

Requires Python 3.11 or later, Git, and an agent that supports `SKILL.md` skills. The repository root is the skill directory; retain `SKILL.md`, `scripts/`, and `references/` together.

For a user-local Codex installation on Linux or macOS:

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/ForgeMechanic/truth-seeker.git "$HOME/.agents/skills/truth-seeker"
cd "$HOME/.agents/skills/truth-seeker"
python3 -m venv .venv
.venv/bin/python -m pip install .
```

On Windows, in PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME/.agents/skills" | Out-Null
git clone https://github.com/ForgeMechanic/truth-seeker.git "$HOME/.agents/skills/truth-seeker"
Set-Location "$HOME/.agents/skills/truth-seeker"
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install .
```

Point the agent at that virtual environment's Python when running helpers. Alternatively, activate the environment and use the installed `truth-seeker` command. Installation explicitly downloads the declared dependencies; the review workflow never installs anything automatically. An offline environment can use an approved prepopulated Python environment or local dependency wheelhouse instead.

Codex discovers user skills in `~/.agents/skills`; see its [official skill documentation](https://learn.chatgpt.com/docs/build-skills). For other compatible hosts, put this directory in the host's documented skill location and use its normal skill invocation. The core workflow does not require a proprietary host API.

These instructions install the revision you clone. Before these changes are published, use this local checkout or copy it into the host's skill directory; the GitHub default branch may not yet contain the implementation.

## Start using it

Invoke the skill in your agent, for example:

> Use Truth Seeker to establish sources for my parser tests. Use our parser design document and the selected edition of ECMA-335. Ask me where applicability is unclear.

The agent initializes `.truth-seeker/` in your repository, identifies the requested tests with you, and records the chosen sources and relationships. You can also initialize the records yourself. Replace the helper and repository paths below with your paths:

```sh
python /path/to/truth-seeker/scripts/truth-seeker.py --root /path/to/consumer init
```

The helper needs the installed dependencies in that interpreter. On Windows use the virtual environment's `Scripts/python.exe` and quoted paths. See the [helper interface](references/helpers.md) for record examples and direct Python usage.

Once sources are established, ordinary reviews use that set. New documents are incorporated only on request:

> Add these two design documents to our sources of truth. Bring conflicts with existing sources to me.

A newly added document does not automatically override an existing one.

## Choose what to review

Request one test, a group, a directory, or the whole repository:

> Review the metadata tests against our established sources. Keep the review within that directory.

Prior work is reused when its basis still applies. Changes to tests, relevant sources, or governing decisions trigger reconsideration; implementation-only changes do not. Section relationships allow selective review, while tests linked to a whole document are reconsidered when that document changes.

> Perform a fresh review of these tests even if nothing has changed.

A fresh review reexamines the requested scope without expanding it or changing accepted decisions. No tests or implementation are automatically executed or modified. Architectural expectations must come from established documents, not the agent's preferences. A feature missing from a vision statement is not a contradiction by omission alone.

Not every test needs an independent specification. Unlinked tests are not reported as gaps unless you ask for that examination.

## Work offline

External sources have URLs but do not have to be downloaded by Truth Seeker. Supply artifacts through an independently populated cache outside the repository and Git.

> Review these tests in cache-only mode. Use repository references and cached evidence. Do not attempt network access.

Cache-only mode prohibits availability checks, version checks, downloads and network fallback, including tools used by the agent outside the Python helper. Missing evidence is reported without pretending the assessment was completed. A broken URL does not delete a source or its history.

Set `TRUTH_SEEKER_CACHE` or pass `--cache` to choose a cache root; `--shared-cache` adds read-only roots. After explicitly establishing an external source, import a supplied artifact without network access:

```sh
python /path/to/truth-seeker/scripts/truth-seeker.py --root /path/to/consumer --cache /outside/repository/cache --cache-only import standard /path/to/supplied-spec.pdf --sha256 EXPECTED_SHA256
```

The ID `standard` must already identify an established source. If no expected hash is available, omit `--sha256`; the helper still calculates an identity hash. Initial import selects the artifact. Later imports record observations; selecting a replacement requires `--adopt`. Reviewed baselines never advance merely because a cache was updated.

HTTP/HTTPS acquisition requires a separate explicit `fetch SOURCE --allow-network` operation. Authenticated sources can be supplied through manual import. Read [evidence access](references/evidence.md) for cache layout, permissions, format limitations, and available selectors.

## Keep decisions and progress

The agent records unanswered questions and continues independent work. It does not ask again without a relevant change or your request. Accepted differences keep their rationale; rediscovery does not create another action. A covering review can close a fixed to-do, while changing an accepted decision requires your approval. Superseded decisions retain their history.

Results are saved throughout a review. Later invocations reuse completed applicable work after interruptions. Test moves or renames retain history when identity is established; uncertainty prompts a question instead of an assumption.

Explicit source removal preserves decisions and links to remaining sources. Before removing the last source for any decision, the agent reports the affected decisions and count and asks for confirmation. Confirming removal does not authorize deleting those decisions.

Your repository owns its schema-defined JSON in `.truth-seeker/`. Its local `AGENTS.md` explains records and schemas to agents without requiring the installed skill. The root `AGENTS.md` is not modified. Removing the skill leaves your evidence knowledge readable.

## What a review returns

Reports focus on discrepancies, unresolved questions, and action items, with a brief account of newly reviewed work, reused work, required evidence that was unavailable, and unfinished work. A reused contradiction remains a contradiction.

- [Requirements](specs/truth-seeker-spec.md)
- [Implementation plan](specs/truth-seeker-implementation-plan.md)
- [Implementation choices and permissions](specs/implementation-design.md)
- [Validation and known limits](specs/implementation-validation.md)

## License

Copyright 2026 ForgeMechanic.

Licensed under the [Apache License, Version 2.0](LICENSE) (`Apache-2.0`). External standards and cached third-party artifacts retain their own licensing terms and are not part of this project's license grant.
