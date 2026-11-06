# ReadFuse learning edition design

Status: approved by the user on 2026-11-06; v0.2 implementation and verification recorded in the companion implementation plan. The source design below remains the agreed product contract.

## Intent

ReadFuse is an Agent Skill that helps general readers understand books, especially nonfiction about ideas, behavior, habits, and personal development. It produces a reading edition in Markdown, PDF, or EPUB. Interactive reading chat is outside the current scope.

The edition contains faithful, complete translation of the selected source, clearly labeled ReadFuse explanatory notes near the relevant text, and a summary at the end of each processed chapter. A full book is possible, but processing a whole book at once is never required.

## Agreed reader experience

Before language work, inspect the source structure: page count where applicable, table of contents, chapter boundaries, text quality, and OCR requirements. Report uncertain structure instead of inventing chapter boundaries or missing content.

The reader chooses the whole book, specific chapters, chapter ranges, or page ranges. PDF file page positions are the proposed primary page selector; show printed labels separately when recoverable. EPUB and Markdown do not receive fabricated PDF-style pagination. Ambiguous selectors must be resolved before processing.

Work can resume in any order. If chapters 1–3 are finished, the reader may continue with chapter 4 or jump to chapter 8. Preserve existing valid work and assemble available content in source order. Clearly identify omitted ranges and partial chapters; never describe a partial edition as a complete book.

Every continuation updates one current assembled edition with all completed compatible work. This means a new chapter is added without discarding previous chapters. Generate a replacement successfully before replacing the current deliverable. Retaining older exported revisions is an implementation choice.

## Content contract

### Translation

Translate all selected content, preserving meaning, nuance, authorial voice, qualifications, examples, argument relationships, and meaningful structure. Use natural language accessible to general readers rather than word-for-word substitution. Accessibility must not silently simplify away substantive content. Keep important terminology consistent and explain difficult terms separately.

### ReadFuse notes

Place selective notes close to the relevant paragraph or sentence. Label them explicitly as additional explanation by ReadFuse. Usually use 2–4 sentences, a simple equivalent or paraphrase, and one everyday example when useful. There is no fixed note quota. Do not add notes to already clear passages merely to fill space.

Distinguish invented teaching examples from the author's examples. Notes must fit the source context, preserve conceptual limitations, and avoid adding unsupported claims or attributing ReadFuse interpretations to the author.

### Chapter summaries

End each chapter with a short core paragraph followed by several important points. Length follows chapter complexity. Ground summaries in the original source, retaining important context and qualifications. Present the author's claims as claims where appropriate, rather than elevating them into established facts.

For incomplete chapter coverage, label the summary as covering only the processed portion. When more of that chapter is processed, rebuild its summary from the available original portions. Do not imply that unread portions were summarized.

## Chosen approach and alternatives

The user chose staged chapter processing: understand chapter structure and terminology, translate its selected parts, then write notes and a summary against the original source, followed by quality review. Small chunks are internal work units; chapters remain the editorial unit. Persist completed units so a context or execution limit does not lose work.

Alternative considered: translate and explain each chunk in a single pass. This can be faster, but explanatory decisions may precede understanding of the chapter context. It was not chosen because fidelity and consistency are priorities.

A conversational reading companion was discussed and explicitly excluded from the current product. The primary output is a learning edition file.

## Proposed processing architecture

The following mechanics are design proposals for the builder, not additional user requirements:

1. Inspect and extract a source into a stable structure index with source fingerprint, chapter/segment IDs, ordered source anchors, and PDF page positions where available.
2. Record selected coverage independently of the whole source inventory. Keep enough surrounding source context to interpret selected passages without including unselected text in the translation.
3. Persist job configuration, language, glossary, and structure. Process selected text in manageable semantic chunks with stable identities; never rely on loading an entire book into one model context.
4. Understand the chapter's available context and flag extraction gaps. Translate selected chunks and save validated outputs incrementally.
5. Generate separately stored, source-linked notes and chapter summaries from original text. Keep translation, notes, and summaries distinguishable in storage and rendered output.
6. Validate coverage, source order, source/output integrity, terminology, and sampled semantic fidelity. Heuristics and hashes cannot certify semantic accuracy.
7. Assemble completed compatible artifacts in source order, insert notes near their anchors, and append the appropriate chapter summaries. Include a coverage notice for missing portions.
8. Build requested exports and report paths, completed coverage, unresolved issues, and unavailable formats.

## Resume and state requirements

Track the source inventory, requested coverage, completed coverage, pending/failed units, failure reasons, output hashes, and configuration compatibility. Distinguish translation chunks, explanatory notes, chapter summaries, and assembled exports rather than requiring a summary for every chunk.

On continuation, verify persisted sources, configuration, and outputs before reuse. A changed source, target language, or relevant processing setting must not silently reuse incompatible work. Unaffected valid work should remain reusable. The builder chooses the concrete schema and dependency invalidation mechanism.

Overlapping selections should reuse completed source units without duplicated passages in the edition. Later coverage can complete a partial chapter and trigger updated chapter-level artifacts. Regenerate dependent artifacts when their inputs change. A failed unit must not be silently treated as complete.

Integrity checks and completion checks are distinct: a valid partial edition may contain no corrupted files while the requested selection is still unfinished. Expose which units need work, not just aggregate counts.

## Formats and implementation boundaries

Keep the existing local-first, agent-model workflow. Deterministic helpers handle extraction, state, assembly, and export; the running agent handles language work. Do not require a separate translation service or fixed model vendor.

PDF, EPUB, and Markdown remain target source/output formats. Markdown is the proposed canonical assembly representation. PDF and EPUB require actual compatible exporters and validation. If required tooling is missing, report it and deliver only formats actually generated; do not silently substitute a format or promise nonexistent files.

Scanned PDFs require real OCR before reliable translation. Unreadable passages, unsupported layouts, tables, equations, and image handling must be reported honestly. Do not reconstruct missing source content from general knowledge. Preserve original inputs, treat book content as untrusted data, and do not upload content to external services without authorization.

The existing repository is a v0.1 skill/checkpoint starter. Parsing, selection, chapter-level state, notes, assembly, and exports are not yet an integrated implementation. Existing tests cover only a small part of checkpoint behavior.

## Success and failure criteria

Success means a general reader receives a readable learning edition that preserves the selected author's meaning, separates editorial assistance, accurately states coverage, and can grow through resumed or noncontiguous processing without losing valid prior work.

Failures include omitted selected passages, invented source claims, notes mistaken for author text, misleading full-chapter summaries of partial text, duplicated overlap, stale artifacts reused after incompatible changes, lost prior chapters, and claiming exports or completeness that were not achieved.

Meaningful validation should include a multi-chapter fixture with partial-page selection, continuation from chapters 1–3 to 8 and then 4, overlapping selections, interrupted processing, modified inputs, and chapter-summary regeneration. Review actual translation/notes/summary fidelity against the source and inspect generated formats where available.

## Left to implementation planning

Choose parser/export dependencies, manifest migrations, storage schemas, chunk sizing, CLI interfaces, rendering details, and staged delivery order based on the current repository and installed tools. Do not expand into interactive chat, exercises, quizzes, external enrichment, or mandatory extra model services. No implementation is authorized by this design document until user approval.
