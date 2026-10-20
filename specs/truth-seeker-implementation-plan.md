# Truth Seeker Implementation Plan

**Status:** Proposed implementation plan  
**Governing requirements:** [Truth Seeker Requirements Specification](truth-seeker-spec.md)

Build Truth Seeker as a portable Agent Skill with Python helpers for persistent records, evidence identity, review selection, and cache management. The agent performs the adversarial assessment and user interview. The first milestone should demonstrate a complete review using local evidence; later milestones extend that working path until it meets all current acceptance scenarios.

This plan does not change the specification. Technical choices below are proposals for implementation, not previously accepted requirements. No implementation, installation, commit, or publication is part of preparing this plan.

## 1. Responsibilities and deliverables

| Component | Responsibility | Boundary |
| --- | --- | --- |
| `SKILL.md` | Identify when Truth Seeker applies, locate existing records, establish requested scope and access mode, and route the workflow | No mandatory host-specific tools or autonomous expansion of sources |
| Supporting references | Explain source establishment, alignment review, interviews, and decision handling where detailed guidance is needed | Load relevant guidance rather than the whole specification on every invocation |
| Python helpers | Initialize and validate records, identify input versions, resolve recorded evidence, select affected reviews, save progress, manage cache artifacts, and calculate source-removal impact | Do not infer semantic relationships or decide which conflicting claim should prevail |
| Consumer knowledge base | Store versioned JSON and local schemas in `.truth-seeker/`, including readable local instructions | Remains understandable without the skill; contains no external document cache |
| External cache | Retain identified artifacts and retrieval metadata outside the repository | Can be populated independently; never requires network access for review |
| Tests and evaluation fixtures | Verify deterministic behavior and exercise realistic agent workflows | Python tests alone do not establish the quality of AI reasoning or interviews |
| Distribution documentation | Explain prerequisites, installation, permissions, dependencies, cache behavior, and supported operations | No hidden installation or publication |

The skill uses its host agent's reasoning. Building a separate AI service, model API client, or autonomous reviewer process is unnecessary for this design.

## 2. Proposed technical foundation

Resolve these choices while building the foundation, before records or interfaces depend on them. Record the choices and rationale in repository design documentation without rewriting them as user requirements.

| Area | Proposed starting point | Work needed before adoption |
| --- | --- | --- |
| Python | Python 3.11 or later | Confirm the supported range and exercise it in CI |
| JSON validation | JSON Schema Draft 2020-12 with a declared validation dependency | Select the validator, check licensing, and ensure local schema resolution never fetches remote schemas |
| Content identity | SHA-256 for file and section bytes, with Git identities as additional repository context | Define precisely which bytes are hashed and how section extraction is versioned |
| Persistent format | A versioned local manifest referencing JSON records and bundled schemas | Choose file boundaries and ID conventions; keep independent records practical to update without loading all tests |
| Record writes | Validate updates, use atomic file replacement, and detect stale writes | Decide whether any operations need multiple-file coordination and test interrupted updates |
| Executable helpers | A small source-based Python interface usable by an agent or directly | Select invocation and packaging; do not promise a CLI before it exists |
| Test locations | Portable repository-relative locators plus logical test identities and recorded reconciliation | Establish a bounded initial identification method without requiring a test-runner plugin |
| External cache | Configurable root with hash-identified objects and source/version metadata | Choose default OS locations, import format, and retention behavior |
| Document access | Local Markdown first; identified local PDF, HTML, and Word artifacts next | Select parsing dependencies and define supported selectors and extraction limitations |

Do not require a universal semantic test-discovery engine. The agent can identify the requested tests and propose relationships; helpers validate and persist explicit records. Initial support may be bounded, but it must not be described as complete across every language or document format.

## 3. Implementation sequence

### Milestone 1 Establish the persistent model and skill entry point

Define enough of the record model to support one real investigation without repeatedly changing identities or conflating findings with decisions.

Implement:

- A concise `SKILL.md` with standard name and description frontmatter, repository discovery, scope selection, cache-only restrictions, and links to relevant workflow guidance.
- Initialization of `.truth-seeker/`, local schemas, and its `AGENTS.md`. Leave the consumer's root instructions alone.
- Stable identities and references for sources, tests or assertions, relationships, review results, questions, decisions, and to-dos. These are logical entities; their JSON file boundaries remain an implementation choice.
- Separate observed evidence versions from versions actually examined in a review.
- Separate a finding's conclusion from user acceptance, supersession, and completion of review work.
- A representation for evidence locators and relationship scope that accommodates a whole document, a section, or an architectural relationship.
- Validation of both JSON structure and cross-record references, with explicit format versions.
- Validated writes that preserve the previous usable state when an update fails. Detect stale updates rather than silently overwriting another writer's work.

The decision model must permit a decision to exist without a source after a user-confirmed removal. Choose how to represent that state without deciding what such a decision should mean for the user. Do not implement automatic deletion of shared decisions or choose the unresolved policy for other shared findings.

**Completion evidence:** Initialize a temporary consumer repository, record and reload a small investigation, reject invalid references, and read the result through local instructions without the installed skill. Verify that malformed updates do not destroy earlier records.

### Milestone 2 Complete one local alignment review

Build a complete skill workflow around local Markdown documents and a user-selected group of tests. Test selection need not execute the consumer's tests to demonstrate alignment review.

Implement the workflow to:

1. Read existing records and establish the requested test scope and source-access mode.
2. On first use, help establish sources and relationships through reasoning and user questions. On later runs, use recorded sources unless additional exploration is requested.
3. Read the selected assertions, relevant source passages, and applicable decisions in manageable groups.
4. Compare test assertions with the sources and compare applicable sources with each other. Include documented architectural responsibilities rather than judging only functional success.
5. Ask targeted questions about applicability and genuine conflicts. Save unanswered questions and continue independent work.
6. Record results reasonably soon after an addressed unit of work, including the evidence versions actually examined.
7. Produce a report emphasizing discrepancies, unresolved questions, and actions, with newly reviewed, reused, and unavailable-evidence summaries.

Do not report an unlinked test as a gap by default. Do not treat a feature absent from a vision statement as a contradiction. Do not create a task for a discrepancy already covered by an applicable decision.

**Completion evidence:** Walk through fixtures containing an aligned test, a conflicting assertion, conflicting documents, an intentional difference, an architectural placement conflict, and an unlinked test. Check the saved records and report, not merely the wording of the skill instructions.

### Milestone 3 Add selective review and resume behavior

Implement deterministic comparison of recorded review inputs with current inputs. Review selection should return the reason each item needs examination or can reuse previous work, leaving the semantic assessment to the agent.

Implement:

- Selection within a single test, an explicit group, a directory, or the repository.
- Comparison of test content, relevant source content, and governing decisions against the basis of a completed review.
- Section-aware source comparisons where locators are supported, and document-level comparisons for recorded whole-document relationships.
- A fresh-review override that reexamines the selected scope without acquiring sources or changing accepted decisions.
- Resume behavior that distinguishes completed results from unfinished work and reevaluates whether saved inputs still apply.
- Test move and rename reconciliation that carries history only for established identity. Ambiguous identity becomes a user question.
- A compact selection summary so thousands of tests do not all need to enter the agent's context on every run.

Propose comparison behavior for dirty working trees and for a recorded section that can no longer be resolved before relying on either. Never silently treat unresolved evidence as unchanged, or invent a narrower relationship to skip work. Preserve test identity independently of the content version so an established rename does not hide a behavioral edit.

**Completion evidence:** Review a fixture, change one relevant section, and demonstrate the exact affected test selection. Repeat with an unrelated section change, a decision change, an implementation-only change, a fresh-review request, and an interruption followed by restart. Add a synthetic large inventory to verify that selective output does not require sending the whole corpus to the agent; do not invent an acceptance threshold for runtime or token cost.

### Milestone 4 Implement source cache and explicit acquisition

Implement external-artifact storage and identity without coupling review to network access.

Deliver:

- Configurable cache roots outside consumer repositories, portable references in committed records, and independently populated cache import.
- Metadata associating source identity and URL with local content hash, known version, retrieval time, and update-check information when available.
- Imported hash verification and continued access to identified older versions needed by prior reviews.
- Local resolution that distinguishes available evidence, unavailable evidence, and inability to check remote currency.
- A separate explicit acquisition or refresh path. Choose supported URL schemes and authentication boundaries before implementing that path; avoid committing credentials in source records.
- Conditional update checks where the source supplies useful metadata. Do not claim a local hash can establish remote freshness.
- A network boundary that prevents availability checks, version checks, redirects, downloads, or fallback acquisition in cache-only mode.

Cache import and source establishment are different operations: putting bytes in a cache must not automatically establish a new source of truth. Similarly, fetching a new version must not advance a reviewed baseline.

**Completion evidence:** Import a local artifact with a URL without contacting that URL; reuse it repeatedly; reject a hash mismatch; preserve an older reviewed artifact after refresh; and continue with a cached artifact whose remote URL fails. In cache-only tests, make attempted network use fail the test even when the cache is missing or incomplete. Exercise permitted acquisition against controlled local HTTP fixtures rather than depending on public sites.

### Milestone 5 Support external document evidence

Extend the local review path to the external evidence types in the specification, using cached bytes.

Implement and document:

- PDF, HTML, and Word document text extraction using declared, inspectable dependencies.
- Whole-document references and progressively more precise section locators where they can be resolved reliably.
- Deterministic handling of duplicate or missing selectors without silently choosing a different passage.
- Extraction provenance sufficient to connect a reviewed passage to the identified original artifact and parser behavior.
- References to external implementation code at identified revisions when established by the user as evidence, without turning this into a standalone implementation audit.

Original artifact identity and extracted text identity serve different purposes. Keep extraction results rebuildable while retaining the original version used for a review. Do not advance baselines solely because a parser or extraction index changes.

**Completion evidence:** Review small, redistributable PDF, HTML, and Word fixtures offline, covering duplicate headings, missing sections, and extracted passages tied to original hashes. Use original or appropriately licensed fixtures rather than committing third-party standards. A format or selector that is not implemented must be documented as unsupported rather than guessed.

### Milestone 6 Complete decision and source maintenance

Implement explicit record operations and agent workflows for the lifecycle rules that span reviews.

Deliver:

- Explicitly requested source additions, including conflicts with existing sources and user-selected roles and applicability.
- Persistent unanswered questions with recorded context, so relevant changes can be distinguished from unrelated changes and repetition alone does not prompt another interview.
- Reuse of accepted differences without duplicate actions, and presentation of genuine new disagreements without changing the accepted decision.
- User-approved decision replacement that retains superseded rationale and identifies the replacement and reason.
- Closure of a fixed to-do based on a later review covering the same material, recording the evidence and preserving accepted decisions.
- Location updates for unavailable sources without changing their logical identity.
- Source-removal impact calculation that identifies decisions losing their last source and reports their count before asking for confirmation.
- Confirmed removal that removes source-specific records and updates relationships, while retaining decisions, rationale, and remaining source links.

For a proposed removal, calculate impact before mutating records and verify that the confirmed impact is still applicable when applying the change. The source-removal confirmation must not be interpreted as authorization to delete affected decisions. Ask how to handle decisions left without sources; if unanswered, preserve them and the unresolved question. Shared findings whose removal behavior has not been decided must be surfaced for clarification rather than assigned an invented policy.

**Completion evidence:** Exercise the transition sequences in acceptance scenarios 8–13, 17–18, and 21. In particular, remove one of three supporting sources and retain the decision; then propose removing its last source and verify that no removal occurs before impact confirmation. Verify that confirmed removal still does not delete the decision.

### Milestone 7 Validate the portable skill and prepare distribution

Establish GitHub Actions coverage as soon as executable helpers exist; extend it through each milestone rather than waiting until the end.

Deliver:

- Unit tests for content identity, relationship traversal, record validation, affected-review selection, lifecycle operations, and cache policy.
- Integration tests for initialization, local and cached evidence, progress preservation, source maintenance, and reporting inputs across Windows, macOS, and Linux.
- Filesystem cases including spaces, Unicode names, platform separators, cache paths outside the repository, and invocation from different working directories.
- Behavioral exercises with a real agent using the skill and temporary consumer fixtures. Check recorded outcomes, scope, user questions, decision preservation, and attempted side effects.
- A standard skill-format validation pass for frontmatter, references, and unfinished scaffold content, alongside behavioral evaluation.
- Concise installation and usage documentation, supported Python and document-format details, and declared file, network, subprocess, and dependency behavior.
- A selected license before release and a source-only installation check. Publication remains a separate authorized action.

Keep agent-specific UI metadata optional. Validate the core workflow without requiring a particular proprietary host integration. Behavioral exercises should cover reasonable paraphrases of user requests; tests that merely search for required words in `SKILL.md` are not sufficient.

**Completion evidence:** All deterministic checks pass on the supported OS matrix, all specification acceptance scenarios have evidence, and a fresh temporary consumer can follow the documented source installation and complete an offline review. When only one agent host has been exercised, describe that limit rather than claiming execution validation on every host.

## 4. Acceptance coverage

Scenario numbers refer to section 11 of the requirements specification as it stands when this plan is written.

| Requirement group | Specification scenarios | Primary milestones |
| --- | --- | --- |
| Initial source establishment and explicit additions | 1, 8, 9 | 2, 6 |
| Requested scope and explicit fresh review | 2, 5 | 2, 3 |
| Change triggers and section or document selection | 3, 4 | 3 |
| Unlinked tests, missing evidence, and architectural alignment | 6, 7 | 2, 4, 5 |
| Interviews and unresolved questions | 9, 10 | 2, 6 |
| Accepted differences, supersession, and to-do closure | 11, 12, 13 | 2, 6 |
| Interrupted review and test identity | 14, 15 | 1, 3 |
| External cache, offline mode, and unavailable sources | 16, 17 | 4, 5 |
| Removal impact and decision preservation | 18, 21 | 6 |
| Independent readability of consumer records | 19 | 1, 7 |
| Platform tests and inspectable distribution | 20 | 7 and every executable milestone |

## 5. Decisions to settle during implementation

Resolve decisions close to the milestone that needs them. No additional feature scope is implied by these questions.

- Before milestone 1 records become a persistent contract: Python baseline, schema validator, record boundaries and IDs, format versions, write strategy, and representation of decisions left without sources.
- Before milestone 3 reuse is relied upon: test identity and content boundaries, dirty-working-tree handling, section comparison rules, and unresolved-selector behavior.
- Before milestone 4 acquisition is enabled: URL schemes, cache root and object layout, import metadata, update checking, and cache retention and sharing behavior.
- Before milestone 5 formats are advertised: parser dependencies, supported locators, and known extraction limitations.
- Before source removal involving shared findings: user-approved handling of those findings; decisions already have explicit preservation requirements.
- Before distribution: helper invocation and package layout, supported versions, installation procedure, license, and release authorization.

## 6. Initial implementation target

Start with milestones 1 and 2: a working skill entry point, locally readable schema-defined records, and one complete scoped review of tests against local Markdown evidence. Include a targeted interview, an unresolved question that does not halt independent work, incremental saves, and the required report.

That target is a foundation, not a claim that the complete specification has been implemented. Continue through selective reuse, external evidence, lifecycle operations, and cross-platform validation before declaring full coverage.

Standalone implementation audits, mutation testing, generated test experiments, periodic autonomous audits, and automatic exploration of new sources remain outside this plan.
