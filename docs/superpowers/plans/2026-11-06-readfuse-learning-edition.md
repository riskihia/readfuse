# ReadFuse Learning Edition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the existing skill/checkpoint starter into an agent-operated learning-edition workflow with source inspection, selected coverage, resumable translation, anchored explanatory notes, chapter summaries, and cumulative exports.

**Architecture:** Keep language generation in the running agent. Python helpers index local sources, persist source-addressed artifacts, invalidate dependent work, and assemble one current reading edition. Implement Markdown first, then EPUB/PDF adapters under the same contract; do not label the workflow complete until format adapters and meaningful export checks are exercised.

**Tech Stack:** Python 3.10+, unittest, standard-library JSON/hash/filesystem/XML/ZIP utilities; optional PyMuPDF for PDF text extraction; optional Pandoc and an installed Unicode-capable PDF engine for exports. Do not install dependencies until needed during execution.

**Spec:** `docs/superpowers/specs/2026-11-06-readfuse-learning-edition-design.md`

## Execution status

Implemented in the current workspace on branch `readfuse-learning-edition`; user staging is preserved and no commits/pushes were made. Test scenarios are grouped under concrete test names in `tests/` rather than retaining every illustrative name in this plan. Optional dependencies were installed locally in ignored `.readfuse-deps` for real PDF/EPUB checks.

Independent review found four Important issues (PDF boundaries, reserved/aliased paths, translated headings); reproductions were added before fixes. Heading artifacts are an additional shared contract required per selected chapter. PDF export uses sanitized Pandoc HTML and PyMuPDF Story, not LaTeX. Privileged Windows symlink coverage is explicitly skipped; ordinary hardlink aliases and actual second-process lock contention are tested. Broad multilingual semantic accuracy and rich layout fidelity are not certified.

The original short Indonesian example is available under `.readfuse-jobs/demo/edition/` in all three formats. PDF layout was visually inspected; EPUB container/spine/content was validated and re-inspected, without claiming a graphical EPUB-reader check.

## Global Constraints

- Interactive reading chat is outside the current scope.
- A full book is possible, but processing a whole book at once is never required.
- EPUB and Markdown do not receive fabricated PDF-style pagination.
- Ambiguous selectors must be resolved before processing.
- Usually use 2–4 sentences, a simple equivalent or paraphrase, and one everyday example when useful. There is no fixed note quota.
- End each chapter with a short core paragraph followed by several important points.
- Integrity checks and completion checks are distinct.
- Keep the existing local-first, agent-model workflow.
- No fixed model service, no invented source text, no unauthorized external uploads, and no source overwrites.
- Preserve valid existing work, label partial coverage, and rebuild cumulative output in source order.

## Review Focus

- Overlapping page selections must reuse source units without duplicating paragraphs (Tasks 1–3, 7).
- Two chapters can share a PDF page; page selection must include both matching portions without assuming exclusive chapter page ranges (Tasks 1–2).
- Symlink escapes, malformed persisted state, and output aliases must fail without damaging existing work (Tasks 3–5).
- Interrupted or concurrent updates must preserve the latest valid checkpoint/deliverable (Tasks 3, 5).
- A failed exporter or unsafe embedded source reference must preserve existing exports and never trigger remote retrieval (Tasks 1, 5–7).

## File responsibilities and shared contracts

Create a small `scripts/readfuse/` package: `sources.py` indexes source content; `selection.py` resolves scopes; `state.py` manages validated artifacts and persistence; `assembly.py` renders Markdown; `export.py` invokes local exporters; `cli.py` exposes the workflow. `scripts/readfuse_cli.py` is the executable entry point. Retain `scripts/checkpoint.py` as a version-1 compatibility utility; never reinterpret old jobs as version 2 silently.

Use JSON-compatible dictionaries at module boundaries, with schema validation at input boundaries:

- `Index`: `version: 2`, original source SHA-256/format, `page_count` (PDF only, otherwise null), ordered chapters `{id, title, segment_ids}`, ordered segments `{id, chapter_id, ordinal, text, sha256, anchors}`, and inspection warnings. An anchor records source offsets or PDF file page position (1-based), optional printed label, and extraction provenance. A segment is the smallest selectable stable unit; work chunks group segment IDs without changing identities.
- `Selection`: ordered, deduplicated `segment_ids`, affected chapter IDs, and per-chapter full/partial coverage. Chapter selectors use indexed IDs. CLI translates displayed ordinal chapter numbers to those IDs explicitly.
- `Config`: source and target languages, mode (`learning`, `translate`, `summarize`), notes policy, and rendering settings. `learning` is the normal learning-edition mode; do not silently change existing explicit translation/summary requests.
- `State`: persisted index fingerprint/config, cumulative selected IDs, source and artifact hashes, per-unit failures, revision, and dependency fingerprints. Translation records cover ordered segment IDs; notes identify a translated segment anchor; chapter summaries record the exact source coverage they summarize. No-notes decisions are explicit reviewed records, not missing work.
- `Report`: integrity issues, pending/failed/stale IDs, requested coverage complete, and whole-book coverage complete. Chapter summaries and note reviews count toward learning-mode completeness.

These are implementation decisions proposed here, not claims that the user specified the schema. All paths recorded for generated artifacts must resolve inside the job directory. External source input is read-only. Never use network fetches to resolve document resources.

Workspace currently has no `.git`; do not initialize a repository or make commits implicitly. At each task boundary, if the user has supplied an existing Git checkout by execution time, commit only that task's changes; otherwise leave reviewed files in place and report this limitation.

### Task 1: Stable source inventory and inspection

**Files:** Create `scripts/readfuse/__init__.py`, `scripts/readfuse/sources.py`, `tests/test_sources.py`, `tests/fixtures/learning-book.md`. Add small locally generated PDF/EPUB fixtures in tests where appropriate.

**Interfaces:** Produce `inspect_source(path: Path) -> dict` (`Index`) and `validate_index(index: dict) -> None`. Other tasks consume their validated output.

- [x] Write failing unittest cases: `test_markdown_keeps_front_matter_and_eight_chapters` (all non-heading source text represented once); `test_repeat_inspection_has_same_ids`; `test_pdf_file_pages_differ_from_printed_labels`; `test_chapters_can_share_page`; `test_epub_spine_order_not_zip_order`; `test_scanned_pdf_reports_ocr_needed`; `test_epub_external_entities_and_path_escape_rejected`. Assert inventory covers captions/footnotes when recoverable and warns on unsupported rich content.
- [x] Run `python -m unittest discover -s tests -p test_sources.py -v`; confirm failures concern absent behavior, not broken imports/fixtures.
- [x] Implement Markdown heading/paragraph indexing, EPUB spine-driven local ZIP/XML extraction with remote resources disabled, and optional PyMuPDF extraction. Use recoverable PDF outline/heading evidence; uncertain chapters remain explicit and require reviewed boundaries. Keep source units no larger than a PDF page portion so page selections do not include neighboring pages. Keep context separate from selected output.
- [x] Validate input/index schemas and deterministic ordering. Warn on uncertain extraction order, images/tables/equations that are not preserved, and encrypted/unsupported sources. A missing PDF parser must give an actionable dependency error. OCR is reported as needed, not implemented or claimed.
- [x] Run the targeted suite; exercise the PDF tests against the optional parser when installed, otherwise report skips explicitly. Checkpoint this task as described above.

### Task 2: Chapter/page selection and resumable coverage

**Files:** Create `scripts/readfuse/selection.py`, `tests/test_selection.py`.

**Interfaces:** Consume `Index`. Produce `select_scope(index: dict, *, chapter_ids: list[str] | None = None, pages: list[int] | None = None, all_content: bool = False) -> dict` (`Selection`) and `merge_coverage(index: dict, existing: list[str], added: list[str]) -> list[str]`.

- [x] Write `test_chapters_one_to_three_then_eight_then_four_source_order`, `test_overlapping_pages_deduplicated`, `test_shared_page_selects_both_chapter_portions`, `test_partial_chapter_marked_partial`, and `test_invalid_ambiguous_or_non_pdf_page_selection_rejected`. Assert missing scope does not default to the whole book and combining page/chapter selectors is rejected rather than guessed.
- [x] Run `python -m unittest discover -s tests -p test_selection.py -v`; confirm expected failures.
- [x] Implement selectors against stable segment anchors, retaining source order. Page positions are 1-based inclusive file positions, with no inferred printed pagination. Return coverage metadata derived from chapter membership.
- [x] Run the suite and checkpoint this task.

### Task 3: Version-2 state, artifact dependencies, and safe continuation

**Files:** Create `scripts/readfuse/state.py`, `tests/test_learning_state.py`; preserve `scripts/checkpoint.py` and its existing tests.

**Interfaces:** Consume Index/Selection/Config. Produce `init_job(job: Path, index: dict, config: dict) -> None`, `extend_selection(job: Path, selection: dict) -> None`, `record_artifact(job: Path, artifact: dict) -> None`, `record_failure(job: Path, unit_id: str, reason: str) -> None`, and `status(job: Path, *, expected_config: dict | None = None) -> dict` (`Report`). Shared internal IO: `load_job(job: Path) -> dict` and `atomic_write(path: Path, data: bytes) -> None`.

- [x] Write tests for completing selected translations without redoing them; notes-review records including an empty reviewed note set; chapter rather than chunk summaries; summary invalidation when chapter coverage grows; changed target language/source detection; unrelated chapters remaining reusable after one artifact changes; failure reasons; output/source hash tampering; no version-1 silent migration; corrupted state; symlink/path escapes; source/checkpoint/other-artifact alias rejection; interrupted atomic writes and simultaneous writers.
- [x] Run `python -m unittest discover -s tests -p test_learning_state.py -v`; confirm the new assertions fail before implementation.
- [x] Implement schema validation, artifact dependency fingerprints, explicit incompatible-job errors, and immutable source inventory for each job. Changed original source requires reinspection into a separate job; do not merge different editions automatically. Rendering changes invalidate exports only. Extend selected coverage idempotently; stale summaries cannot count as complete.
- [x] Use atomic replacement and an exclusive per-job mutation lock with explicit lock ownership. Refuse a second writer cleanly; do not auto-delete a potentially active lock. Validate recorded artifact paths against all source/state paths and prevent multiple logical artifacts from aliasing one mutable file. Validate notes' segment anchors and summaries' source coverage.
- [x] Keep `verify` integrity and `complete` coverage separate in the report; expose concrete pending/stale/failed IDs and both selection/book completeness. No claim of semantic QA from hashes.
- [x] Run all state tests plus `python -m unittest discover -s tests -p test_checkpoint.py -v`; checkpoint this task.

### Task 4: Learning-edition skill instructions and editorial contract

**Files:** Modify `SKILL.md`, `references/architecture.md`, `references/translation.md`, `references/summarization.md`, `references/quality.md`; create `references/explanations.md`; update `assets/manifest.example.json` to a documented v2 example once schema is implemented (retain a legacy example only if README still needs it).

**Interfaces:** Instructions consume the Index, Selection, State and Report contracts and generate artifact files accepted by `record_artifact`. No direct LLM API runner is added.

- [x] Update the workflow to inspect first, show chapter/page options, resolve requested scope, and stage chapter understanding, translation, notes, summaries, QA, and assembly. Persist chapter context/glossary; pass manageable chunks and necessary adjacent context, never a whole book prompt.
- [x] Define faithful meaning-based translation: preserve qualifications, authorial voice, arguments and all selected passages. Define selective labeled notes (usually 2–4 sentences, simple equivalents/examples); record reviewed absence of notes. Define summaries as a core paragraph plus important points from original covered source, labeled partial where required.
- [x] Replace the old requirement to deliver translation and summary as separate books for learning mode. Keep translation-only/summary-only modes when explicitly requested. Document which helpers are implemented versus agent responsibilities, scope selection, noncontiguous resume, and cumulative exports.
- [x] Manually exercise instructions on an original short fixture: produce one translation, one labeled note, and a partial chapter summary, then compare every claim against the source. Check that an opinion/qualified claim is not promoted to fact. Do not test exact instructional wording.
- [x] Run `python C:/Users/LENOVO/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`; resolve actual format issues. Review reference routing for selective loading and checkpoint this task.

### Task 5: Ordered Markdown edition with anchored notes and chapter summaries

**Files:** Create `scripts/readfuse/assembly.py`, `tests/test_assembly.py`.

**Interfaces:** Consume validated job/artifacts. Produce `assemble(job: Path) -> Path` for `job/edition/book.md`. Use state's atomic IO/lock and integrity report.

- [x] Write `test_edition_order_one_two_three_four_eight`, `test_notes_follow_matching_segment_and_are_labeled`, `test_summary_follows_chapter`, `test_partial_chapter_and_missing_ranges_visible`, `test_overlaps_never_duplicate_text`, `test_stale_summary_not_rendered_as_current`, and `test_failed_assembly_preserves_previous_edition`. Assert input files and unrelated artifacts remain unchanged, including symlink output cases.
- [x] Run `python -m unittest discover -s tests -p test_assembly.py -v`; confirm expected failures.
- [x] Assemble all valid completed translations, notes and current summaries in source order, regardless of the latest requested scope. Keep original chapter titles distinct from editorial headings and source footnotes distinct from ReadFuse notes. Show coverage and missing/stale editorial components honestly; never insert invented content to fill gaps.
- [x] Validate dependencies before publication and use successful temporary output then atomic replacement. Refuse corrupted artifacts rather than silently dropping them. Keep the previous edition until a replacement is ready.
- [x] Run the suite, inspect the actual Markdown fixture result, and checkpoint this task.

### Task 6: Local EPUB/PDF exports with honest capability reporting

**Files:** Create `scripts/readfuse/export.py`, `tests/test_export.py`; modify `references/export.md`.

**Interfaces:** Produce `capabilities() -> dict` and `export_edition(job: Path, formats: list[str]) -> dict` with per-format successful paths/failures and the assembled edition fingerprint. Consume `assemble` output; do not call language services.

- [x] Write tests for missing Pandoc/PDF engine, argument-list subprocess invocation, nonzero process exit, malformed/empty output, escaped output paths, external image references/raw active content, and preserving existing exports on failure. Assert success is recorded only for validated artifacts with the current edition fingerprint.
- [x] Run `python -m unittest discover -s tests -p test_export.py -v`; confirm failures.
- [x] Invoke installed Pandoc with explicit arguments and no shell interpolation. Export only from staged job-local resources; reject remote references and unsafe source markup before rendering, and do not enable arbitrary filters or commands. Use an installed appropriate PDF engine; unsupported target scripts/font coverage require explicit warnings or failure, not a claim of readability.
- [x] Validate EPUB ZIP structure, container/OPF/spine links and reading order; validate PDF page count/text availability using the PDF parser. Stage and validate before replacing each current format. Record failures separately, retaining old exports with an explicit stale status.
- [x] Run unit tests and real exporter integration checks when dependencies are installed. Inspect beginning/middle/end, notes, summaries, Unicode text, and navigation in generated artifacts. If dependencies are unavailable, report the unverified format; do not claim complete PDF/EPUB support. Checkpoint this task.

### Task 7: Integrated CLI, continuation scenario, and documentation

**Files:** Create `scripts/readfuse/cli.py`, `scripts/readfuse_cli.py`, `tests/test_learning_workflow.py`; modify `README.md`, `references/architecture.md` and examples to match actual CLI.

**Interfaces:** CLI commands: `inspect --source PATH --index PATH`; `init --job-dir PATH --index PATH --config PATH`; `select --job-dir PATH (--chapters 1-3,8 | --pages 10-15 | --all)`; `status --job-dir PATH`; `record --job-dir PATH --artifact PATH`; `fail --job-dir PATH --unit-id ID --reason TEXT`; `assemble --job-dir PATH`; `export --job-dir PATH --formats md,epub,pdf`; `verify --job-dir PATH [--require-complete]`. `status` reports pending work without error; `verify` fails for integrity problems, additionally for unfinished requested work with `--require-complete`.

- [x] Write an integration fixture in original/public-domain prose with eight chapters. Inspect, initialize, select 1–3, record agent-written learning artifacts, assemble, restart in a new process, select 8, then 4. Assert prior artifact hashes remain unchanged and current edition order is 1,2,3,4,8 with uncovered chapters labeled.
- [x] Add partial PDF page/overlap continuation, empty selection errors, malformed config/artifacts, source/config mismatch, failed then retried work, same-chapter summary regeneration, and interruption recovery. Use real parser-generated fixtures for page behavior. Demonstrate local-only behavior and no source modification.
- [x] Run `python -m unittest discover -s tests -p test_learning_workflow.py -v`; confirm failures before wiring commands.
- [x] Implement thin CLI routing to earlier interfaces with validated arguments and machine-readable reports. Large language tasks remain explicit steps for the host agent; CLI never pretends to translate by itself. Show errors with actionable paths/IDs and nonzero exits, not stack traces for normal input errors.
- [x] Update README with an executable end-to-end example and current dependency/capability boundaries. Separate legacy checkpoint usage from v2 learning jobs. Reflect the actual partial/full coverage and output behavior, not aspirational roadmap claims.
- [x] Run `python -m unittest discover -s tests -v`, all CLI `--help` paths, skill validation, real available format integration checks, and a source-vs-output editorial review on the short learning fixture. Explicitly list skips/dependencies and semantic limitations. Review the complete diff for unintended changes; checkpoint this task.

## Plan self-review

Source inspection/selection are covered by Tasks 1–2; resumability/config compatibility and dependencies by Task 3; language quality and artifact separation by Task 4; cumulative editions by Task 5; formats by Task 6; real continuation by Task 7. Shared signatures and JSON contracts are defined above and reused by name. Review-focus failure modes have tests assigned to their owning tasks. The plan does not require implementing a commercial LLM runner, interactive reader, or OCR system.

## Execution handoff

Review this plan before implementation. Recommended method: native execution in this session, since the tasks share a compact schema and sequential dependencies; use `superpowers:executing-plans`. Subagent-driven execution remains an option if the user explicitly chooses it. A final independent review must check the integrated result and actual verification evidence. No automatic repository initialization or unrequested publication.
