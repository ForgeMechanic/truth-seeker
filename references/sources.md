# Sources and interviews

For initial use, read existing JSON before asking the user what already exists.
Identify the requested tests and sources with the user. No test comments, framework
adapter or consumer test execution is required: a locator can be an entire file, a
Python qualified symbol, or an explicit line range. Framework-neutral file or line
locators are conservative; do not claim automatic identity across languages.

A source record names its role and scope: normative standard, compatibility reference,
project design, or another user-established role. A selected edition remains selected
until intentionally changed. There is no universal authority ordering.

Ask only questions needed to establish applicability or resolve a real conflict.
Examples: do these passages govern the same behavior? Does the project intentionally
place this responsibility here? Is this project-specific override intentional?
Present both documents and test evidence, with selectors and identified versions.
A test not found is not proof that no test exists.

Use `register sources` with a record of the actual user instruction. Propose links
using `register links` with `status: proposed`. After the user establishes them, use
`establish-link` with their instruction. A statement naming both sources and tests
may already establish the link; do not manufacture a redundant approval question.
For broad architecture links use `nature: architecture`, explanatory rationale and
whole-document scope when finer association is not justified.

Ordinary review must not search for more sources or create unrecorded semantic links.
If the user explicitly requests exploration or adding documents, confine it to that
request. Adding a source does not establish that its claims prevail. Preserve both
conflicting sources, ask about the disagreement, and record the answer as a proposed
then explicitly accepted decision when that is what the user decided.

If the answer is unavailable, use `question`, record the affected tests and/or sources,
and continue independent work. Creating the question records that it has been raised.
`questions` indicates `ask_again` only after a relevant input change. After raising a
changed question, call `mark-asked`; use `--requested` only when the user asked to
reconsider it. Do not repeatedly present it as a demand for an answer. `answer` records
a real user answer; it does not by itself accept a new policy decision.

If a new question or decision changes the context of an active packet, start a new
scoped run rather than recording a result against an outdated snapshot. Completed
results in the earlier run remain reusable when their basis is applicable.
