# Learning-edition quality gate

## Deterministic integrity

Validate source/config fingerprints, segment coverage and order, unique ownership of artifact paths, nonempty UTF-8 output, notes anchors, summary source coverage, and artifact dependencies/hashes. Inspect pending, failed and stale IDs separately. Integrity can pass while selected work remains unfinished; use `verify --require-complete` for selected coverage.

Reject unknown/missing source units, output corruption, unreviewed notes and stale chapter summaries. New chapter coverage requires a refreshed summary; changed translation requires renewed notes review. Never silently drop corrupt artifacts or label incomplete output complete.

## Editorial review by the agent

Compare original text and translation for omissions, changed negations/numbers/causality, lost uncertainty, altered examples, inconsistent terminology and voice. Check representative beginning/middle/end passages plus every known difficult fragment. Expand review where a sample reveals issues. Length/structure checks and LLM self-review do not prove accuracy.

Check each summary claim against its original covered source. Ensure partial coverage is labeled and opinions retain attribution. Check every ReadFuse note for contextual fit, short accessible phrasing and clearly distinguished added examples. Notes must not smuggle new claims into translated prose.

## Source and delivery review

Inspect source extraction before trusting coverage: reading order, OCR needs, footnotes, images, tables and equations. Hashes only prove agreement with extracted text, not faithful extraction of the original book.

Inspect cumulative ordering, missing-range notices, note placement and chapter-end summaries. Open actual requested EPUB/PDF outputs, inspect navigation and beginning/middle/end, and check target-script glyphs/fonts, tables and footnotes. Report unavailable formats and unresolved limitations. Never claim verified semantic accuracy or full-book completeness from helper reports alone.
