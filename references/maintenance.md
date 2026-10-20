# Decisions and source maintenance

## Accepted decisions

Use `register decisions` to propose a decision with statement, rationale, applicable
tests and sources. `accept ID --approval TEXT` records actual user acceptance.
An agent cannot prove human consent with a flag: these fields are an inspectable
record of the interview, not an authentication or sandbox boundary. Never fabricate
approval text or call acceptance merely because AI reasoning seems persuasive.

Accepted decisions cannot be edited through ordinary registration. To replace one,
use `supersede OLD replacement.json --approval TEXT` after user approval. The old
statement and rationale remain, marked superseded, with a replacement link.
Fresh review alone never authorizes this operation.

## Action items

`todo REVIEW DISCREPANCY` creates an action for a finding or returns the existing
matching action without reopening it. A review whose recorded applicable decision
already addresses the discrepancy must not create another action. Record the
applicable decision IDs when completing the finding; exact wording is not a reliable
semantic duplicate detector, so check existing actions and decisions first.

`close TODO LATER_REVIEW REASON` needs a current later supported review of the same
test, claim and source coverage. The agent must verify that it covers the actual
original discrepancy, not merely a different assertion in the same test. Closing a
fixed action needs no user approval and does not modify accepted decisions.

## Relocation and removal

A source that cannot be located is unavailable, not deleted. Use identified cached
bytes when present. Updating a URL for the same identified source uses `relocate
sources`; the old evidence and logical identity remain. Do not search for the new
location without instruction.

Only an explicit source-removal request permits `remove-preview SOURCE`. Read its
impact, including decisions that would lose their last source and shared findings.
If decisions lose their last source, explain which decisions and how many and ask
whether to proceed. `remove` requires that exact current impact token and the user's
confirmation. Re-preview after state changes; do not reuse confirmation for a
changed impact. Source removal does not delete decisions, their rationale or links
to retained sources. Decisions left without sources produce an unresolved handling
question rather than a fabricated new meaning.

If shared findings exist, ask how to handle them because the specification has not
selected a universal policy. `--shared-handling` records explicit instruction to
preserve shared findings and detach the removed evidence. If that is not what the
user wants, leave removal pending until an appropriate implementation/handling
choice is established. Do not use a flag to silently choose policy.

Source-only review history is removed when no shared action depends on it. Shared
review records explicitly retained by instruction lose obsolete source locators and
become ineligible for reuse. No source tombstone is kept; version control retains
past source records. Do not remove external cache objects as an implicit consequence
of removing a source: other consumers may still need them.
