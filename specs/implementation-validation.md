# Truth Seeker implementation validation

The current checkout implements the seven milestones in the [implementation
plan](truth-seeker-implementation-plan.md). This record distinguishes local evidence
from validation still requiring external CI or another agent host.

## Local validation

| Check | Result |
| --- | --- |
| Linux, Python 3.11.17 | 54 tests passed |
| Linux, Python 3.14.4 | 54 tests passed |
| Portable skill and reference validation | Passed |
| Skill-creator structural validation | Passed |
| Isolated helper installation and source-archive smoke exercise | Passed |
| Windows and macOS GitHub Actions jobs | Configured; not yet run |

The automated suite exercises deterministic behavior using temporary consumer
repositories and cache roots. It covers record validity and interrupted writes,
scoped review selection, evidence tokens, resume behavior, decisions and questions,
source-removal impact, cache-only access, controlled HTTP refresh, document extraction,
and portable paths. Public standards are not copied into test fixtures.

Run from an environment with the declared project dependencies installed:

```sh
python -m unittest discover -s tests -v
python scripts/validate-skill.py
```

The skill also passes the skill-creator's structural validator. That check validates
frontmatter and basic skill structure, not the quality of semantic review.

Source archive and pure-Python wheel builds have been exercised. A separate virtual
environment installed the wheel from local bytes without network access, initialized
consumer records using the packaged schemas/instructions, registered sources and
tests, produced a packet, recorded a review, and reused it. The source archive was
also extracted outside the checkout and its direct script initialized another
consumer successfully. Installing helpers does not itself install/discover the
agent skill; source installation retains the root `SKILL.md` and references.

## Agent workflow exercise

`tests/fixtures/alignment/` provides established contract, compatibility and
architecture documents, five test locators, an existing accepted legacy decision,
and a review request with a predetermined user deferral. Prepare an isolated copy:

```sh
python scripts/prepare-evaluation.py /path/to/new/temporary/consumer
```

The preparation script establishes the raw records but does not generate review
conclusions. Read that consumer's `request.md` and invoke the skill against it.

An in-session agent exercise read the packets and recorded:

- Supported valid-input behavior against its contract section.
- An unresolved conflict between invalid-input requirements, preserving the supplied
  user deferral and continuing other work.
- An architectural discrepancy in the Storage validation interface.
- A known legacy contradiction explained by the existing accepted decision, without
  generating another action for it.
- No gap for the extra feature with no recorded source relationship.

After recording completed units and resuming, the report showed one newly reviewed
item, three reused results, one unresolved question that was not eligible to be
asked again, and only the architecture action. The unlinked feature was neither
reported as missing evidence nor assigned an action. The accepted decision remained
unchanged. No consumer test execution or network acquisition was required.

This was an exercise by the implementing agent with a known fixture, not an
independent-agent evaluation or evidence of correctness on arbitrary repositories.
It exposed and led to fixing a scoping bug: a decision or question with explicit
test IDs must not apply to other tests merely because they share a source document.
An automated regression test now covers that boundary.

## Acceptance coverage

The following tests and exercise steps provide evidence for section 11 of the
requirements specification. Test names are in `tests/test_workflow.py` unless noted.

| Scenario | Evidence |
| --- | --- |
| 1 Initial source establishment | `test_explicit_source_and_relationship_establishment`; agent fixture and sources/interview workflow |
| 2 Requested scope | `test_scope_is_a_hard_boundary`; CLI scope integration |
| 3 Reuse and triggers | `test_implementation_only_and_unrelated_test_changes_reuse`; decision-change and dependent-question tests |
| 4 Section and document impact | `test_section_change_only_selects_recorded_dependents`, `test_document_relationship_reopens_on_any_document_change`, exact-artifact provenance test |
| 5 Fresh review | `test_fresh_review_reexamines_without_overwriting_history` |
| 6 No default unlinked gap | `test_unlinked_test_is_not_a_reported_gap`, missing-source test; extra-feature exercise |
| 7 Architectural alignment | Agent fixture's ownership finding and extra-feature handling; documented judgment remains with the agent |
| 8 Explicit source addition | `test_explicit_source_and_relationship_establishment`; source workflow excludes unsolicited additions |
| 9 Conflicting sources | Invalid-input fixture preserves both documents and leaves applicability unresolved |
| 10 Unresolved interviews | `test_questions_are_not_repeated_without_relevant_change`, `test_unanswered_question_does_not_settle_dependents_or_block_other_work` |
| 11 Reused accepted differences | `test_decided_discrepancy_does_not_create_actions`; legacy exercise |
| 12 Decision replacement | `test_decision_changes_trigger_reconsideration_and_preserve_history`; fresh review preserves accepted decisions |
| 13 Fixed to-do closure | `test_fixed_todo_closes_and_rediscovery_does_not_reopen`, `test_todo_closure_requires_covering_current_review` |
| 14 Interruption | `test_resume_reuses_completed_work_only`, failed-write tests; resumed agent exercise |
| 15 Test identity | `test_identity_transfer_requires_establishment` |
| 16 External offline cache | `ExternalEvidence` tests in `test_evidence.py`: no socket/acquisition in cache-only review, independent import, shared-cache reads, hash checks, version selection |
| 17 Missing or moved source | `test_missing_source_is_reported_without_deletion`; URL relocation and refresh-preservation tests in `test_evidence.py` |
| 18 One source removed | `test_removing_one_of_three_sources_preserves_decision`, source-only history removal and shared-finding preservation tests |
| 19 Independent readability | `test_initialize_is_readable_and_non_destructive`; isolated package and source-archive initialization |
| 20 Portability and inspection | CLI/path integration, declared permissions/dependencies, structural validation; actual Windows/macOS runs remain pending |
| 21 Last-source removal | `test_last_source_requires_current_impact_confirmation_and_preserves_decision`, source-only history test, generated unresolved handling question |

## Remaining external validation and supported limits

`.github/workflows/test.yml` defines actual Ubuntu, Windows and macOS jobs for Python
3.11 and 3.14, including source installation, the test suite, skill validation, and
wheel construction. These jobs have not been dispatched by this local implementation
work. Windows/macOS execution and resulting green checks must not be inferred from
Linux success or a valid workflow file.

The skill is agent-independent in its interface, but only the current host's
in-session workflow has been exercised. Other agent hosts and an independent fresh
reviewer remain additional validation opportunities, not results claimed here.

Supported locators and extraction limitations are listed in
[evidence access](../references/evidence.md). No OCR, legacy Word `.doc`, JavaScript
execution, authenticated website login, universal framework discovery, or automatic
semantic test-identity reconciliation is implemented. Whole-document and explicit
locators remain available. These limitations must be reported when relevant rather
than guessed around.

The unresolved handling policy for shared findings is not silently selected. Source
removal requires user instructions when such records are affected. Decisions left
without sources are preserved with an unresolved question. A user may need to make
those project-specific decisions during actual use.

The implementation has not been installed into the user's skill directories,
committed, pushed, or published as part of this work.
