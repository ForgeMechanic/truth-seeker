# Truth Seeker — Requirements Specification

**Status:** Requirements draft under discussion  
**Owner:** ForgeMechanic  
**Intended repository:** `https://github.com/ForgeMechanic/truth-seeker` (existence and public visibility not verified)  
**Distribution:** Public, open-source, source-distributed Agent Skill  
**Implementation:** Python scripts plus `SKILL.md`; no compiled binary distribution

## 1. Purpose and current scope

Truth Seeker adversarially examines an established set of unit tests for a section of code or an entire repository to determine whether their assertions align with designated source-of-truth documents. It identifies discrepancies, examines evidence and assumptions, preserves investigations, and brings unresolved decisions to the user.

A discrepancy does not by itself establish which artifact should change. A test may be incorrect, documentation may be outdated, or the difference may expose an ambiguity or an intentional project decision. Designating a source of truth establishes its role in the investigation without making it infallible.

Alignment includes documented architectural design: component responsibilities, boundaries, and where behavior belongs. A test may demonstrate working behavior while exercising a responsibility in a place that conflicts with the documented design. Functional success alone does not establish architectural alignment. An additional feature is not a contradiction merely because a vision document does not mention it; a discrepancy must be grounded in applicable documented expectations.

Repositories may contain thousands of tests. Persistent knowledge and selective review are core requirements so repeated investigations do not spend AI effort reexamining unchanged evidence or reconsidering decisions whose basis remains applicable.

The current scope is **test-to-document alignment**, including disagreements between applicable sources encountered during that review. It is not a general implementation audit or a requirement to assess every test's defect-detection strength. An implementation-only change does not trigger another alignment review.

The skill must be generic and useful across repositories rather than dependent on any particular project or standard.

**Guiding principle:** Truth is not assumed; it is investigated, challenged, and supported by evidence.

## 2. Evidence and source relationships

Tests, implementations, standards, project documents, reference implementations, and recorded decisions can provide different kinds of evidence. No artifact is universally authoritative. Sources may be outdated, ambiguous, contradictory, or based on the same mistaken assumption. AI reasoning provides hypotheses and interpretations, not self-authenticating authority.

Source authority and applicability are scoped to particular behavior, editions, contexts, and recorded decisions. Distinguish conformance to a standard from compatibility with a reference implementation. A project document may explicitly override an external requirement within a stated scope; retain the rationale rather than assuming one source always prevails. A newer edition or reference implementation does not automatically replace the project's selected basis.

Maintain a repository-wide record of established sources and their relationships to tests and assertions. Sources may include repository documents, external standards such as ECMA-335, PDF and HTML references, external Word documents, reference implementation code such as .NET at an identified revision, and project design decisions.

Relationships may refer to a whole document or a particular section. They may also describe an area's relationship to the overall architectural design without an exact assertion-level or section-level link. A document's title does not determine its role: a vision document may contain concrete architectural expectations. Preserve the nature and scope of the relationship rather than forcing a precise link or assuming an unrecorded one.

Not every test requires a separate source-of-truth document; tests and implementation may be sufficient for the project's purposes. A test with no recorded source relationship is not, by that fact alone, a gap to report or a question to raise. Examine absent source relationships when the user requests it. Distinguish that situation from an established review that cannot proceed because its required evidence is unavailable.

## 3. Establishing and maintaining sources

### Initial identification

On first use, the skill inspects existing evidence JSON records, if present, and helps the user identify the initial source-of-truth documents and relevant relationships. Identifying applicable sources and deciding whether test assertions and document passages concern the same behavior are judgment-based activities performed through the AI skill workflow. They do not require automated semantic-discovery tooling. Listing test artifacts is distinct from deciding what they mean or which sources govern them.

Preserve the resulting knowledge for reuse. Once sources are established, ordinary reviews use that set. Do not seek additional sources or add newly encountered documents without instruction. Claims of violations must be grounded in established sources or recorded decisions, not unstated architectural preferences. Before applicable sources are established, source identification is preparatory work rather than a basis for declaring violations.

### Explicit additions and exploration

Support a request such as “I have added these documents; incorporate them as sources of truth.” Limit that activity to the requested documents and scope. Further source identification or relationship exploration occurs when requested and may be limited to a small area, such as one test or document section. All exploration respects source-access restrictions, including cache-only mode. The invocation syntax is undecided.

If a newly added source conflicts with an existing source, retain both and bring the conflict to the user. Do not assume that the newer or more recently added document overrides the other. Record the user's decision and rationale, or preserve the conflict as unresolved if they cannot decide.

### Source identity, availability, and removal

External sources must be addressable by a URL. The URL identifies an origin or possible retrieval location; it does not require fetching or imply current availability. Supported URL schemes remain undecided.

Record source identity, location, kind, applicable revision or edition, role and scope, and content identity. Keep the latest observed version distinct from versions actually reviewed. Record retrieval and licensing information where known.

An unreachable URL or a document that cannot be found does not establish deletion. Preserve the source's identity and history. A moved URL can be replaced without discarding that history; any requested effort to find a replacement location respects the exploration and access restrictions.

When the user explicitly requests removal of a source, or confirms that they deleted the document and want it removed from the source set, remove its source record and source-specific history from the active knowledge base, subject to the impact confirmation below. Do not retain it solely as an archive or tombstone; version control provides the historical record. Source-specific history does not include decisions merely because they reference that source.

Removing a source does not remove the decisions it supported. Update relationships involving the removed source while preserving the decisions, their rationale, and their relationships to retained sources. For example, if three documents support a decision and one is removed, the decision remains with its other two source relationships.

Before removing a source, determine whether the removal would leave any recorded decisions with no remaining sources. If so, identify the affected decisions, state how many would lose their last source, explain the consequence, and ask the user whether to proceed. Do not carry out that removal until the user confirms. Confirmation to remove the source is not permission to delete the decisions. Preserve them and ask the user how they should be handled when no sources remain; do not silently discard or reinterpret them.

## 4. Review scope and interview

The user may request a review of a single test, a group of tests, a directory, or the whole repository. Keep the review within that scope. Shared evidence and changes affecting other tests do not automatically expand it.

Within the requested review, compare applicable sources as well as test assertions. For example, document A may describe behavior exercised by a test while document B appears to describe conflicting behavior with no corresponding test identified. Examine whether they concern the same behavior and expose the disagreement or possible coverage issue. Do not equate a test not yet found with an established absence of coverage, or turn this into a general search for undocumented tests.

An interview with the user is part of the skill. Present relevant evidence and ask targeted questions when applicability, relationships, or conflicting requirements require a decision. Questions may concern whether two descriptions refer to the same behavior, which requirements apply, or whether a difference is intentional or requires action. Do not silently decide through automated linking.

If the user cannot answer, record the question as unresolved and continue with work that does not depend on the answer. Do not decide on their behalf or treat dependent conclusions as settled. Do not ask again unless the user requests it or relevant tests, sources, or recorded decisions change. Preserve the question without requiring a repeated interview on each run.

## 5. Findings, decisions, and action items

Findings distinguish:

- **Supported:** Applicable evidence supports the assertion, without claiming exhaustive proof.
- **Contradiction:** Assertions conflict within an applicable scope; identify the disagreement without automatically deciding which artifact should change.
- **Ambiguous:** The evidence or applicable contract permits unresolved interpretations.
- **Insufficient evidence:** Evidence needed for the requested alignment assessment cannot be established; preserve the limitations without fabricating authority. This does not make an unlinked test a reportable gap by default.

Record the assertion or question, affected tests and sources, supporting and conflicting evidence, relevant revisions, reasoning and limitations, review status, and any decision or next action.

Preserve a discrepancy's disposition: an intentional accepted difference, an issue requiring action, or an unresolved question. Record its rationale, scope, applicable evidence versions, and any resulting to-do. An accepted difference remains a difference rather than becoming apparent alignment.

When the same discrepancy is found again and an applicable decision already addresses it, reuse that decision and rationale. Rediscovery alone must not create or reopen an action item.

A later review covering the same material may close an open to-do when it finds that the discrepancy has been fixed, without explicit user approval of the closure. Record the evidence and reason. This does not authorize replacing an accepted user decision.

If a review disagrees with an accepted decision, preserve the decision and raise the disagreement with supporting evidence for the user's consideration. Replacing or overturning it requires the user's approval. A request for a fresh review is not that approval. When the user approves a replacement, keep the previous decision and rationale in the history, mark it superseded, and identify its replacement and why it changed. Explicit source removal follows the separate rule in section 3.

AI proposals must not silently become accepted user decisions. Reviewing does not authorize automatic fixes to source documents, implementation, or tests. Recording review progress, questions, and findings, preserving user answers, and closing fixed to-dos are part of the review workflow; they are distinct from editing the reviewed artifacts or changing accepted decisions.

## 6. Incremental review and interruption

### Reuse and triggers

Record which tests or assertions were examined against which sources at which versions, with their conclusions, decisions, and unresolved questions. Merely recording that a file was seen is insufficient.

Changes to tests, their relevant sources, or governing recorded decisions trigger reconsideration of affected reviews within the requested scope. Implementation-only changes do not. Compare versions and content identity rather than relying on dates alone. Git commit identities, blob identities, and content hashes can establish the reviewed basis and detect changes.

Use recorded relationships to select affected tests:

- When section-level relationships are known, revisit tests tied to the changed section.
- When a test is linked only to the whole document, a change to that document triggers reconsideration of that test.
- Tests linked only to other unchanged sections are not revisited because of that change.
- Do not assume an unrecorded relationship or infer a narrower scope to exclude a document-linked test.

A change prompts reconsideration; it does not automatically disprove the previous conclusion. Observing a new revision or refreshing a cache does not mark that revision reviewed or advance a reviewed baseline. Reusing a prior investigation preserves its uncertainty as well as its conclusions.

By default, reuse prior work whose basis remains applicable and distinguish it from new or never-reviewed work. The user may explicitly request a fresh review within a chosen scope even when nothing has changed. Fresh review does not expand the scope, override source-access restrictions, or authorize changing accepted decisions. Additional source or relationship exploration still requires instruction.

### Progress preservation

Save completed results throughout the investigation, reasonably soon after work is addressed, rather than waiting for the entire review to finish. If an agent stops mid-review, a later invocation should reuse recorded completed work where applicable and continue unfinished work within the requested scope.

Distinguish completed results from unfinished work. The goal is to reduce repeated investigation and token expenditure, not to recover every in-progress reasoning step or require a write after every observation. Exact save timing and recovery mechanisms remain undecided. Recording progress does not imply acceptance of a proposal.

### Test identity

Carry review history across a test rename or move when it can be established that it is the same test. If identity is uncertain, ask the user rather than assuming the previous review applies. Unanswered identity questions follow the unresolved-question rules. Establishing identity preserves history but does not exempt changed test content from review.

## 7. External cache and cache-only mode

External documents are stored in a persistent, configurable local cache **outside the repository and outside Git**. Repository evidence records contain references, fingerprints, review knowledge, and decisions rather than copies of external artifacts. Respect licensing and access controls; accessibility does not grant redistribution rights.

Truth Seeker need not acquire cached documents itself. The cache may be independently populated where network access is available and made available in a restricted, secure, sandboxed, or air-gapped environment. Keep machine-specific cache paths out of shared records. Exact default location and cache layout remain undecided.

Associate cached artifacts with source identity and URL, content hash, retrieval time where known, last update-check time where known, and available version or remote change metadata. Independently populated artifacts remain usable when some retrieval metadata is unavailable. Preserve identified old versions where needed to reproduce reviews. Verify imported content hashes; a matching hash establishes byte identity, not publisher authenticity.

Reuse cached content across investigations. Acquisition and update checking are separate, explicit activities, never silent consequences of review. When checking is permitted, available remote version or change metadata may avoid unnecessary downloads. A local hash alone cannot show whether remote content changed; without suitable remote metadata, determining that may require downloading it again. An older selected edition is not invalid merely because a newer one exists.

In **cache-only mode**, both Python tooling and the agent workflow may use only repository-local sources and external artifacts already present in the configured cache. They must not attempt availability checks, version checks, downloads, refreshes, or other network requests. A URL or missing artifact does not authorize network fallback.

If a source is unreachable but a usable cached copy exists, continue against that identified version and report when remote availability or currency could not be checked. If required evidence has no usable local or cached copy, report it as unavailable under the current mode and preserve the unresolved work. Missing evidence establishes neither agreement nor disagreement.

## 8. Persistent records and self-description

Maintain the consuming repository's knowledge base in `.truth-seeker/`, using JSON with associated versioned JSON Schemas. Both Python tooling and agents must be able to work with those records. Preserve sources, recorded relationships, investigations, findings, decisions and rationale, reviewed versions, questions, action items, and progress needed to reuse completed work.

Keep authoritative knowledge and its schemas in version control. Keep external artifacts and rebuildable caches or indexes outside version control. Records must be portable and understandable without installing the skill or accessing the internet. Validate structure and record references, and do not silently reinterpret accepted decisions when formats change. Exact document boundaries, schemas, and storage layout beyond `.truth-seeker/` remain undecided.

Place self-description in `.truth-seeker/AGENTS.md`, explaining how to locate and interpret records and schemas, source relationships, cache restrictions, decisions, and editing rules. Do not modify the consuming repository's root `AGENTS.md` unless requested. The installed skill must explicitly look for `.truth-seeker/`; nested instructions alone do not ensure discovery from elsewhere in the repository.

Include skill-installation information linking to the intended public project, verifying publication before describing it as published. Reading the data does not require installation. Do not download or execute tooling merely because the local instructions mention it. Removing the skill must not make the repository's evidence data unreadable.

## 9. Review report

Focus on discrepancies, unresolved questions, and action items. Give a brief summary distinguishing:

- What was reviewed during this invocation.
- What reused applicable prior work.
- What could not be reviewed because required evidence was missing, identifying the missing evidence and affected scope.

An absent source relationship is not missing evidence to report by default. Showing an existing unresolved question is not a renewed demand for an answer. Previously accepted differences remain distinguishable from unresolved work, and an already decided discrepancy does not become a new action item just because it appears again.

## 10. Portability and distribution

Truth Seeker is intended for a public, open-source repository under ForgeMechanic, separate from private personal skills and System Design Foundry. The intended project name and skill identifier are **Truth Seeker / `truth-seeker`**. Repository existence and public visibility are not assumed. Do not create, push, or publish a repository without explicit authorization.

Follow standard Agent Skills conventions with `SKILL.md` as the entry point and readable Python scripts for supporting operations. Core workflows and evidence records must not depend on a particular agent product or proprietary host API. The skill provides adversarial reasoning and interviews; Python supports deterministic operations rather than independently performing AI judgment.

Support Windows, macOS, and Linux. Account for platform differences in paths, cache locations, subprocess invocation, and text handling without embedding machine-specific assumptions in shared records. Document the Python requirement and declared dependencies. No compiled binary distribution, hidden downloads, automatic dependency installation, or opaque executable components.

Include unit and integration tests for the Python tooling, covering initialization, source resolution, cache-only operation, persistent records, and platform assumptions. Run applicable tests in GitHub Actions on actual Windows, macOS, and Linux runners, including paths with spaces, Unicode filenames, and platform-specific path conventions.

Make shipped source, imports, subprocess use, file permissions, and network behavior inspectable and documented. An open-source license must be selected before release; no final license choice is established here.

## 11. Acceptance scenarios

1. On initial use, the skill consults existing evidence JSON, helps establish sources and relationships, and asks about judgment calls. Subsequent runs reuse that knowledge without repeating source exploration.
2. The user requests review of one test, a group, a directory, or the repository. Review remains within that scope even when shared sources affect tests elsewhere.
3. Tests, sources, and governing decisions remain unchanged. Prior work is reused. Implementation-only changes do not trigger review; relevant test, source, or decision changes do.
4. One source section changes. Tests linked to that section and tests linked only to the whole document are reconsidered. Tests linked only to unchanged sections are not reconsidered because of that change. No unrecorded relationship is assumed, and no baseline advances merely because a change was observed.
5. The user explicitly requests a fresh review of unchanged material. That scope is examined again while source-access restrictions and accepted-decision protections remain in force.
6. A test has no independent specification or recorded source relationship. Its absence is not reported as a gap unless requested. Required but unavailable evidence for an established relationship is reported separately.
7. Tests show functional success but conflict with documented architectural responsibilities. The discrepancy is raised. A feature omitted from a vision document is not a contradiction by omission alone.
8. New documents appear after the sources are established. Ordinary review does not incorporate them. An explicit request to add specified documents starts the source-establishment workflow for those documents.
9. A newly added source conflicts with an existing source. Both remain recorded; neither automatically prevails because of recency. The user's decision and rationale are saved, or the conflict remains unresolved.
10. The user cannot answer an interview question. It is saved as unresolved, dependent conclusions remain unsettled, and independent review work continues. The question is not asked again without a request or relevant change.
11. A recorded project-specific override or accepted difference explains a discrepancy. Its rationale and scope are reused; rediscovery does not create or reopen an action item.
12. A review disagrees with an accepted decision. That decision is preserved and the disagreement is raised. Only user approval permits replacement; the previous decision and rationale remain marked as superseded, with the replacement and reason identifiable.
13. A later review covering the same material finds an open to-do's discrepancy fixed. It can close the to-do without explicit approval, recording the evidence and reason without overturning an accepted decision.
14. An agent stops before completing a review. Results saved during the review remain available; a later invocation reuses applicable completed work and distinguishes it from unfinished work.
15. A test moves or is renamed. History carries over when identity is established; uncertain identity prompts a question rather than an assumption that an old review applies.
16. An ECMA-335 PDF or other external source is cached outside Git and reused offline. An independently populated cache works in a restricted environment. Cache-only mode permits no network requests or automatic acquisition, even for missing artifacts.
17. A source URL stops resolving. Its identity and history are preserved, a usable cached version remains usable, and a replacement location can retain the same source identity. If no usable copy exists, dependent work remains unresolved.
18. The user removes one of three sources supporting a decision. The removed source's record and source-specific history are removed from the active knowledge base, while the decision, its rationale, and its relationships to the other two sources remain. Prior versions of the removed source records remain in version control.
19. Another agent can locate the knowledge base through its local self-description and interpret the JSON and schemas without the skill or internet access. Uninstalling the skill preserves readable evidence data.
20. The Python tooling's applicable unit and integration tests run on Windows, macOS, and Linux through GitHub Actions. Shipped source and declared file, network, and subprocess behavior are inspectable.
21. A requested source removal would leave recorded decisions without any remaining sources. Truth Seeker identifies the decisions and their count, explains the impact, and requests confirmation before removing the source. Even after confirmation, the decisions are preserved; how to handle them is brought to the user rather than decided through automatic deletion.

## 12. Open questions and undecided details

The following are not settled requirements or selected implementation designs:

- How to represent decisions with no remaining sources after a confirmed removal, following the user's handling decision; how source removal affects other shared findings beyond the decision-preservation and relationship rules above.
- The exact representation and acceptance process for proposed source relationships, beyond the established interview and user-decision rules.
- Test identification and reconciliation methods across languages and frameworks; no mandatory test adapter or runner-execution approach is selected.
- How to locate and compare document sections reliably, including duplicate headings and differing PDF or HTML structures.
- Supported external-source URL schemes, default cache location, cache configuration interface, import metadata format, retention details, and shared-cache behavior.
- Save timing and mechanisms for preserving completed progress across interruptions.
- JSON file boundaries, manifest design, schema dialect and field conventions, extension format, and migration mechanisms.
- Hash algorithm and cache object layout; content hashes are required, but a specific content-addressable storage design is not selected.
- Minimum Python version, external dependency policy, and document parsing libraries.
- Command names, flags, Python entry points, package layout, and installation details.
- Final open-source license and release plan.

## 13. Broader ideas set aside

The original draft also considered standalone implementation or documentation audits, mutation testing, boundary and negative-test generation, metamorphic and differential experiments, and periodic broad audits or sampling. These are possible future discussions, not current requirements, scheduled milestones, or authorization to expand a review.

This document defines requirements for discussion. It does not direct implementation, select a CLI design, or authorize publication.
