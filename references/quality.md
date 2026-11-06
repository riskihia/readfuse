# Learning-edition quality gate

## Deterministic integrity

Validate source/config fingerprints, segment coverage and order, unique ownership of artifact paths, nonempty UTF-8 output, notes anchors, summary source coverage, and artifact dependencies/hashes. Inspect pending, failed and stale IDs separately. Integrity can pass while selected work remains unfinished; use `verify --require-complete` for selected coverage.

Reject unknown/missing source units, output corruption, unreviewed notes and stale chapter summaries. New chapter coverage requires a refreshed summary; changed translation requires renewed notes review. Never silently drop corrupt artifacts or label incomplete output complete.

## Editorial review by the agent

Compare the original and target for every sentence and meaningful clause in the entire selected coverage; a beginning/middle/end sample is not enough to establish completeness. Keep them visible side by side. Record substantive omissions, additions, meaning/detail changes and source uncertainty with brief source/target evidence. Sentence splitting or merging is acceptable when each claim and relationship remains represented.

Check negation, modality, certainty, quantifiers, attribution, actors/referents, causality, contrast, conditions, sequence, properties, direction, position, examples, terms, references, numbers and voice. Then compare once more after fluency edits, including paragraph/list restructuring. Revisit notes when their translation changes and verify summary claims against the original selected passages. Separate an actual meaning problem from acceptable style variation. Length/structure checks, hashes and LLM self-review do not prove accuracy.

If a semantic review record is requested, its checklist documents that the agent performed these checks against the current source and artifacts. A passed record is not an independent accuracy certification; unresolved substantive findings require `needs_revision`.

Check each summary claim against its original covered source. Ensure partial coverage is labeled and opinions retain attribution. Check every ReadFuse note for contextual fit, short accessible phrasing and clearly distinguished added examples. Notes must not smuggle new claims into translated prose.

## Source and delivery review

Inspect source extraction before trusting coverage: reading order, OCR needs, footnotes, images, tables and equations. Hashes only prove agreement with extracted text, not faithful extraction of the original book.

Inspect cumulative ordering, missing-range notices, note placement and chapter-end summaries. Open actual requested EPUB/PDF outputs, inspect navigation and beginning/middle/end, and check target-script glyphs/fonts, tables and footnotes. Report unavailable formats and unresolved limitations. Never claim verified semantic accuracy or full-book completeness from helper reports alone.
