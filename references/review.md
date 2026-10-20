# Alignment review

1. Use `plan` for a read-only selection or `start` to save a review run. The helpers
   paginate inventory output. Choose a scope corresponding to the user's request,
   not the scope of every test affected by shared evidence.
2. Reuse matching completed results unless a fresh review is explicitly requested.
   Inspect `show reviews ID` or applicable decisions when necessary; do not load all
   history by default. Unlinked tests are not reportable gaps unless requested.
3. For each pending item, obtain `packet RUN TEST`. Read its exact assertions,
   source passages, relationship rationale, prior decisions, and unresolved questions.
   The packet's `basis_hash` binds the evidence read. Blocked items identify missing
   evidence; do not browse or refresh automatically.
4. Challenge alignment: what does each assertion require? Does the relevant source
   actually say that, under this edition and scope? Do the applicable sources agree?
   Do the tests reveal responsibility or boundary placement at odds with the
   documented design? Do not substitute personal architecture preferences or a
   missing feature description for a documented conflict.
5. Apply accepted decisions where they explain the same discrepancy. Distinguish a
   known accepted difference from a genuine new disagreement with the decision. The
   latter is a proposed finding for user consideration, never a unilateral reversal.
6. Ask targeted questions if required. Record unanswered questions, link them to
   dependent results, leave those conclusions unsettled, and continue other work.
7. Call `complete` after each completed meaningful unit, using the packet token and
   explicit claim, outcome, reasoning, limitations, and relevant decision/question
   IDs. Do not advance baselines just because content was observed. A stale token
   means re-inspect the changed evidence in a new run.
8. Record a to-do only for actionable discrepancies not already governed by a
   decision. Use `report RUN --markdown` as a factual report skeleton. Explain the
   discrepancies, questions and next actions, and summarize reviewed/reused/missing
   and unfinished work. Reading the report is not authorization to re-ask unchanged
   questions. A reused contradiction remains a contradiction.

`complete` records a finding, not user acceptance. Use `ambiguous` when applicable
interpretations remain unsettled; `insufficient-evidence` when the requested
assessment lacks needed evidence. A blocked investigation can be recorded but is
not reusable as a successful completed alignment review.

Scope and progress are explicit per run. To resume after interruption, start a new
run in the requested scope; completed compatible results are reused automatically.
No finalization command is needed to make earlier completed results durable.

A pure test file move may reuse history after identity is established. Use
`relocate tests` with the actual basis for established identity. If uncertain, ask
and record the question; do not transfer history by resemblance alone. Content
changes still prompt reconsideration even when logical identity is established.
