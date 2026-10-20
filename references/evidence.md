# Evidence access and selectors

Review, planning, packets, reports and extraction only read local bytes. No evidence
helper fetches embedded links, schemas, PDF attachments, HTML resources, or Word
relationships. The agent must honor the same boundary with its other tools.

## Cache

Pass `--cache PATH`, set `TRUTH_SEEKER_CACHE`, or use the user default:

- Windows: `%LOCALAPPDATA%/truth-seeker/Cache` (home fallback when unset).
- macOS: `~/Library/Caches/truth-seeker`.
- Linux: `$XDG_CACHE_HOME/truth-seeker` or `~/.cache/truth-seeker`.

The path must be outside the consumer repository. `--shared-cache PATH` adds
read-only search roots; writes go only to the primary root. Shared roots can be
supplied as mounted read-only storage. Read operations do not create a writable
cache. No committed record contains these machine-specific root paths.

An established external source has a URL, kind, role, scope, optional edition and
selected `object_hash`. Use `import SOURCE FILE --sha256 HASH` to prepopulate from
an independently supplied file. The hash option verifies a known expected hash;
computed hashes identify bytes, not publisher authenticity. Missing provenance is
recorded as unknown, not fabricated. Import does not create a source or establish a
semantic relationship.

Cached bytes are never converted to the host's line endings. Extracted text uses LF
endings for consistent text hashes across checkouts; raw artifact hashes continue to
identify the exact original bytes.

`fetch SOURCE --allow-network` is a separate explicitly authorized acquisition
operation. It supports HTTP, HTTPS and local `file:` URLs; remote file hosts require
manual local import. URLs must not contain credentials. Public HTTP acquisition
uses system TLS trust and normal proxy environment configuration; custom login
flows are not implemented. Use independently obtained artifacts for authenticated
sources. Do not place secrets in committed URLs or acquisition metadata.

Requests have a 30-second timeout and a 64 MiB document limit. Conditional HTTP
requests use ETag/Last-Modified only when their previously cached object is usable.
An unavailable URL preserves the cache. Original bytes and per-version provenance
are retained; there is no automatic garbage collector.

Initial import or fetch selects the first available object. Later import/fetch
updates `observed` only; `--adopt` explicitly selects new bytes for subsequent review.
Neither operation changes completed review records. Do not adopt a different standard
edition or overwrite the selected evidence merely because it is newer.

`--cache-only` and `fetch --allow-network` cannot be combined. Without
`--allow-network`, fetch fails before any URL access. Network prohibition also applies
to availability and version checks and to tools outside this helper.

## Locators

Pass a JSON selector file to `extract SOURCE --selector FILE`, or put `selector` in a
recorded relationship. Exactly one selector is permitted; `{}` means whole document.

| Kind | Selectors | Boundary |
| --- | --- | --- |
| Markdown | `{"heading":"Rule"}` or `{"heading_path":["Contract","Rule"]}` | ATX headings; fenced code headings are ignored; duplicate matches are unavailable |
| UTF-8 text or repository code | `{"lines":[10,20]}` | Inclusive, one-based; changes in positions may require clarification |
| Python test code | `{"python":"Suite.test_rule"}` | Qualified AST name, including decorators; duplicate/missing names are unavailable |
| HTML | `{"heading":"Rule"}` or `{"anchor":"rule"}` | Heading elements and heading IDs; no remote resources; UTF-8 input |
| Word `.docx` | `{"heading":"Rule"}` | Standard Heading1–Heading9 styles in document body; no legacy `.doc` or OCR |
| PDF | `{"pages":[2,4]}` or `{"bookmark":"Rule"}` | Inclusive, one-based pages or uniquely bounded bookmark; no OCR or arbitrary semantic section inference |

A section ends at the next peer or ancestor heading. Missing or ambiguous locators
are unavailable evidence, not a guessed passage. Whole-document references remain
usable when no reliable finer selector is available. The helper does not automatically
rewrite a recorded selector to a broader document relationship.

PDF extraction does not establish visual reading order, table semantics, or the
absence of text in scanned pages. HTML does not execute JavaScript. Word extraction
reads text in `word/document.xml`, not headers, comments or embedded objects. For
such documents the agent must state relevant limitations and request usable evidence
rather than infer that extraction proves completeness. Parser and extraction identity
are recorded alongside artifact hashes; changing an index never advances a baseline.
