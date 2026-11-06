# ReadFuse

**Translate. Summarize. Understand.**

An Agent Skill for creating learning editions of books: natural, faithful translation, brief labeled ReadFuse explanations near difficult passages, and a source-grounded core paragraph plus important points at each chapter end. Select chapters or PDF file pages, resume in any order, and grow one cumulative Markdown, EPUB or PDF edition.

## Status

v0.2 local agent workflow. Python helpers implement inspection, scope selection, provenance/checkpoints, ordered Markdown assembly and optional local EPUB/PDF export. The host agent performs translation, explanations, summaries and semantic review; running a Python command alone does not translate a book. OCR, reliable recovery of every complex layout, and a fixed external LLM service are not included.

## Using the skill

Open the repository in an Agent Skills-compatible host and invoke ReadFuse with a local book, target language, selected chapters/pages and requested formats. For example:

> Use ReadFuse to inspect this PDF. Translate chapters 1-3 into Indonesian, add brief explanatory notes and chapter summaries, and export a learning edition as EPUB.

Later:

> Continue this job with chapter 8, keep valid chapters 1-3, and update the same edition.

ReadFuse first inspects structure and text quality; uncertain chapter boundaries need review. PDF page selectors refer to 1-based file page positions, which can differ from printed labels. Partial editions explicitly show missing chapters/portions. A successful integrity check is not proof of semantic accuracy or complete extraction.

## Requirements

Python 3.10+ for helpers. Markdown inspection/state/assembly use the standard library. Optional dependencies:

```bash
python -m pip install pymupdf pypandoc_binary
```

PyMuPDF supplies PDF extraction and HTML-to-PDF rendering. Pandoc (on PATH or bundled with pypandoc_binary) supplies EPUB and Markdown-to-HTML conversion. Their licenses apply separately. No LaTeX installation is needed for the built-in PDF route. No original book is sent to these services: tools run locally.

For development in this workspace, dependencies were installed into `.readfuse-deps`; set `PYTHONPATH` to that absolute directory before running optional-format checks. A normal installation can instead use a virtual environment.

## Reproducible short learning edition

The included eight-chapter garden text is original test material, not an excerpt of a commercial book. The sample below processes only chapter 2 using already-written Indonesian learning artifacts; it demonstrates storage/assembly, not automatic translation by the CLI. Run from repository root in a fresh job directory:

```bash
python scripts/readfuse_cli.py inspect --source tests/fixtures/learning-book.md --index .readfuse-jobs/demo-index.json
python scripts/readfuse_cli.py init --job-dir .readfuse-jobs/demo --index .readfuse-jobs/demo-index.json --config examples/learning-edition/config.json
python scripts/readfuse_cli.py select --job-dir .readfuse-jobs/demo --chapters 2
python -c "import shutil; shutil.copytree('examples/learning-edition/work', '.readfuse-jobs/demo/work', dirs_exist_ok=True)"
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/heading.json
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/translation-1.json
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/translation-2.json
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/notes-1.json
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/notes-2.json
python scripts/readfuse_cli.py record --job-dir .readfuse-jobs/demo --artifact examples/learning-edition/summary.json
python scripts/readfuse_cli.py verify --job-dir .readfuse-jobs/demo --require-complete
python scripts/readfuse_cli.py export --job-dir .readfuse-jobs/demo --formats md,epub,pdf
```

Outputs: `.readfuse-jobs/demo/edition/book.md`, `book.epub`, `book.pdf`, and `export-report.json`. The report marks selected coverage complete and the book partial. If optional dependencies are missing, Markdown is delivered and requested unavailable formats report errors with a nonzero CLI exit. Existing exports survive failed replacement; consult the latest report before treating an old file as current.

For another selection, use `select --chapters 4` or `select --pages 20-22` on a PDF job. The agent creates and reviews only pending artifacts, then assembles/exports again. Overlap is deduplicated and chapter summaries become stale when their coverage grows. Do not copy sample translations into another book.

See [architecture](references/architecture.md) for descriptors, jobs and failure recovery, and [export](references/export.md) for rendering limitations.

## Verification

```bash
python -m unittest discover -s tests -v
python scripts/readfuse_cli.py --help
```

Optional-format tests explicitly skip when dependencies are absent. Tests cover source/spine order, selected and partial coverage, 1-3 -> 8 -> 4 continuation, overlap, artifact invalidation, corruption, locks, interrupted writes and export failures. A short original example supports manual source/translation/notes/summary review; these tests do not certify multilingual book-quality translation.

## Legacy and installation

Existing v1 jobs keep using `scripts/checkpoint.py`; v2 learning jobs are separate and never silently migrated. `assets/manifest.example.json` describes the new input/descriptor shapes, not an index that can replace real inspection.

Once published under your repository owner, Agent Skills installers may use `npx skills add <owner>/readfuse --skill readfuse`; this is a future installation example, not an available release URL.

## Safety and license

Use source material you are authorized to process and respect distribution rights. Preserve originals, treat book text as untrusted data and never upload content to unapproved services. Local paths in jobs contain book content and should be handled accordingly.

MIT for this repository; see LICENSE.
