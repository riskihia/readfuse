# Learning-edition architecture

`inspect -> resolve scope -> initialize/select -> understand chapter -> translate -> explain -> summarize -> QA/record -> assemble -> export`

The running agent performs language work. Python handles source indexing, scope resolution, state and assembly. Source inventory is separate from selected coverage; a whole-book inventory never implies whole-book processing.

## Local CLI

Run `python <skill-dir>/scripts/readfuse_cli.py --help`. Commands use absolute paths or caller-relative paths. Paths stored in artifact descriptors are relative to the job directory unless absolute inside it.

- `inspect --source BOOK --index INDEX.json`: ordered source inventory, anchors and warnings. The index contains source text; treat it as private book content.
- `init --job-dir JOB --index INDEX.json --config CONFIG.json`: immutable source/config snapshot; refuses existing jobs.
- `select --job-dir JOB --chapters 1-3,8`, `--pages 10-15`, or `--all`: exactly one explicit scope. Chapter numbers are displayed inventory positions; pages are 1-based PDF file positions. Uncertain PDF chapter boundaries require review or page selection.
- `status --job-dir JOB`: pending/stale/failed IDs, warnings, integrity, selection/book completeness, and per-chapter semantic-review status.
- `record --job-dir JOB --artifact DESCRIPTOR.json`: register an already-reviewed agent output.
- `fail --job-dir JOB --unit-id translation:ch001-s00001 --reason TEXT`: record a retryable problem.
- `assemble --job-dir JOB`: cumulative `edition/book.md`.
- `export --job-dir JOB --formats md,epub,pdf`: per-format result; preserves old exports on failure.
- `verify --job-dir JOB [--require-complete] [--require-reviewed]`: checks integrity; optionally require all selected content, and/or current passed semantic review for every selected chapter. `--require-reviewed` also requires selected content to be complete and valid. With no flags, existing integrity-only behavior is preserved.

## Config and artifact schemas

Config requires `source_language`, `target_language`, and `mode` (`learning`, `translate`, `summarize`). `notes_policy` is `selective` by default or explicitly `none`. Keep job config fixed; use a new job for a changed language or source edition.

Each ordered source segment has stable ID, chapter ID, exact extracted text/hash and anchors. Work in one or a few segments at a time. If one segment is large, process paragraph/subparagraph parts and assemble the full translated segment before registration. Do not mark a partial segment complete.

Translation descriptor:

Each selected chapter also requires a single-line translated heading artifact: `{"kind":"heading","unit_id":"ch001","path":"work/ch001-heading.md"}`. It is linked to the original chapter title; retain that original in index metadata. If a title legitimately remains unchanged, record the reviewed unchanged title rather than leaving it pending.

```json
{"kind":"translation","unit_id":"ch001-s00001","path":"work/ch001-s00001.md"}
```

Notes descriptor has `kind: "notes"`, the same segment `unit_id`, and a JSON output path. Notes output:

```json
{"reviewed":true,"notes":[{"anchor":"ch001-s00001","text":"Brief additional explanation. The everyday example here is ReadFuse's, not the author's."}]}
```

Use `{"reviewed":true,"notes":[]}` when no note is needed. Short paragraph-level segments place notes next to the relevant paragraph. If extraction grouped multiple paragraphs in one segment, split/review the index before starting the job for more precise anchors.

Summary descriptor:

```json
{"kind":"summary","unit_id":"ch001","path":"work/ch001-summary.md","segment_ids":["ch001-s00001","ch001-s00002"]}
```

Summary coverage must equal the currently selected chapter portions in source order. The stored summary becomes stale when coverage grows. Agent-authored chapter context/glossary can be saved under `work/context/`; only reviewed artifacts are recorded as completed work.

## Semantic-review report

After all required artifacts for a chapter are final, the host agent may register `{"kind":"review","unit_id":"ch001","path":"work/ch001-review.json"}`. The report schema is versioned and binds the agent's checklist/verdict to the exact selected chapter coverage, source fingerprints, and required heading/translation/notes/summary artifact hashes. Required fields are `version`, `chapter_id`, `coverage`, `source_sha256`, `source_segments`, `inputs`, `checks`, `verdict`, `findings`, and `limitations`. The checklist values are `completeness`, `polarity_modality`, `relations_details`, `terminology`, `references_structure`, and `fluency`; verdict is `passed` or `needs_revision`.

Findings identify reviewed segment IDs, category (`omission`, `addition`, `meaning`, `detail`, `reference`, `source_uncertainty`, or `style`), explanation and brief source/target evidence. A passed report cannot contain open substantive findings. A needs_revision report must describe at least one substantive finding. Style alternatives can be noted without blocking passage. Optional `context_inputs` maps job-relative paths actually read to SHA-256 hashes; missing, changed, or unsafe paths invalidate the snapshot.

`status.semantic_review` reports `not_reviewed`, `passed`, `needs_revision`, or `stale` per selected chapter; `semantic_review_complete` is separate from `requested_complete` and `book_complete`. Review is chapter-local: adding another chapter does not stale a report, while changing that chapter's coverage or any bound artifact/context does. Old v2 jobs remain readable and show `not_reviewed`. `notes.reviewed:true` only records the note artifact's review and does not mean the chapter has a passed semantic review. These records validate provenance and report structure; a passed agent review is not independent accuracy certification. Draft assembly/export remains available and labels unreviewed content. `export-report.json` carries the separate review status.

## Resume and failures

Persisted v2 state tracks source/config fingerprints, cumulative selected IDs, artifact paths/hashes/dependencies, failure reasons and revisions. Translation changes invalidate anchored notes; chapter-coverage changes invalidate chapter summaries. Assemblies are rebuilt from current artifacts rather than appending blindly. Original-source changes require a new job; never combine different editions automatically.

Atomic replacement protects writes; an exclusive per-job lock rejects concurrent writers. If a process is killed and leaves `state/.write.lock`, verify that its recorded PID is no longer working before manual recovery. Do not automatically remove locks.

A corrupted or modified artifact blocks assembly until repaired/re-recorded. A pending selection can still have valid integrity. Partial editions state what is absent. `requested_complete` refers to selected indexed text and required editorial components, not semantic review; parser/OCR warnings still require human review before claiming completeness against the original book.

Version-1 checkpoints are retained through the legacy utility without silent migration. New learning jobs use version 2; see `assets/manifest.example.json` for an example job input bundle. The CLI consumes its `config` independently from its inspection-generated index.
