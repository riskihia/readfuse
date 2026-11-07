# ReadFuse

[![skills.sh](https://skills.sh/b/riskihia/readfuse)](https://skills.sh/riskihia/readfuse)

**Translate. Summarize. Understand.**

ReadFuse is an Agent Skill that helps readers understand books through faithful, natural translation, brief labeled explanations, and chapter summaries grounded in the original text. Process selected chapters or PDF pages, continue later, and build a cumulative Markdown, EPUB, or PDF learning edition.

**Project status: Beta.** Workflows and output formats may change. Review generated translations and exports before relying on or distributing them.

## Get started

Use the `main` branch for the ready-to-use skill. Open this folder in an Agent Skills-compatible host and ask the agent to use ReadFuse with your local book.

Start by inspecting the source:

> Use ReadFuse to inspect my-book.epub. Show the chapter structure and text-quality concerns. Do not translate until I select the scope.

Then choose the scope and format:

> Process the Introduction into Indonesian with faithful translation, brief ReadFuse explanations, and a chapter summary. Deliver Markdown.

Continue an existing job:

> Continue this ReadFuse job with chapter 8. Preserve completed chapters and update the cumulative edition.

The agent performs language work; Python commands alone do not translate a book. ReadFuse inventories the source before processing it. PDF page positions are 1-based file positions, which may differ from printed page labels. EPUB and Markdown do not have fixed page counts.

## Requirements

Python 3.10 or newer. Markdown inspection, job tracking, and assembly use the standard library. PDF inspection/rendering and EPUB export need optional local dependencies:

```bash
python -m pip install pymupdf pypandoc_binary
```

PyMuPDF handles PDF extraction and rendering. Pandoc, either on PATH or bundled with pypandoc_binary, handles conversion for EPUB and PDF export. No LaTeX installation or separate commercial LLM API is required. The ReadFuse Python helpers process files locally and do not upload book content.

### Third-party licenses

The ReadFuse code in this repository is MIT licensed. Optional tools have separate terms:

- PyMuPDF is offered under AGPL-3.0 or a commercial license. Review its terms before redistributing it or incorporating it into a distributed or hosted product. [PyMuPDF licensing](https://pymupdf.io/licensing)
- The pypandoc Python wrapper is MIT licensed. Pandoc itself is GPL-2.0-or-later; the `pypandoc_binary` package includes Pandoc. [pypandoc licensing and packaging](https://pypi.org/project/pypandoc/), [Pandoc](https://pandoc.org/)

ReadFuse does not bundle either optional tool in this repository. Installing or redistributing them is a separate licensing decision. This summary is informational, not legal advice.

## Included files

- `SKILL.md`: agent instructions and workflow.
- `references/`: translation, explanations, summaries, quality checks, job schemas, and export guidance.
- `scripts/`: local source inspection, resumable jobs, assembly, export, and legacy checkpoint support.
- `assets/`: example input and artifact schemas.

The `dev` branch also contains tests, development examples, and design/implementation documents. Developer instructions are in `docs/development.md` on that branch.

## Outputs and continuation

Jobs store selected coverage and reviewed artifacts under a local job directory, normally `.readfuse-jobs/`. The cumulative edition is written to `edition/book.md`; requested successful exports produce `book.epub` or `book.pdf`. Check the latest `export-report.json` before using an export. Previous exports are preserved when replacement fails.

Translations follow source order. ReadFuse notes are labeled as additions and appear near their source passages. Chapter summaries contain a short core paragraph and important points based on the selected original text. Partial editions identify missing content. Continuing a chapter refreshes dependent summaries and reviews while preserving valid translations.

## Quality and limitations

The host agent compares every selected sentence/clause against the source before and after polishing. Review records bind the review to the exact current source, coverage, and content versions. Translation quality still needs human judgment: a passed agent review records checks, but does not certify accuracy.

```bash
python scripts/readfuse_cli.py --help
python scripts/readfuse_cli.py verify --job-dir PATH_TO_JOB --require-reviewed
```

Integrity, selected-content completion, and semantic-review status are separate. OCR, faithful recovery of every complex layout, and lossless reproduction of images, tables, equations, or typography are not included. Source extraction and rendered exports may require human inspection.

### Book privacy and AI host data

Inspection, job storage, assembly, and export run locally. Translation, explanation, summary, and semantic review are performed by the Agent Skills host. If that host uses a cloud model, it may send selected book passages, nearby context, and generated work to its AI provider under the host's data controls and terms. ReadFuse cannot determine or override those settings. Check the host's privacy terms, use a local model where available, and process only material you are authorized to share with that provider. Do not assume the entire workflow is offline merely because the Python helpers are local.

See [job architecture](references/architecture.md), [quality guidance](references/quality.md), and [export guidance](references/export.md) for details. Existing v1 jobs use `scripts/checkpoint.py`; v2 jobs use `scripts/readfuse_cli.py` without automatic migration.

## Source privacy and license

Preserve original files, process material you are authorized to use, and respect distribution rights. Local job directories (including their generated editions and checkpoints), local dependencies, and agent scratch files are excluded from Git by default. Keep original books outside the tracked repository. Do not place private book content in tracked files or upload it to unapproved services.

ReadFuse source code is licensed under [MIT](LICENSE). See [Third-party licenses](#third-party-licenses) for the optional tools.
