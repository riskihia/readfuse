# Learning-edition export

The canonical edition is `edition/book.md`: faithful translated content, clearly labeled ReadFuse notes close to their segment anchors, and chapter summaries. Assembly includes all compatible completed coverage in source order. It is rebuilt atomically, with missing/partial notices, rather than blindly appending the newest selection.

Run `python <skill-dir>/scripts/readfuse_cli.py export --job-dir JOB --formats md,epub,pdf`.

## Local adapters

- Markdown: standard-library assembly.
- EPUB: installed Pandoc (or pypandoc_binary) builds an EPUB3 with navigation. Validate the ZIP container, package and reading-order links.
- PDF: Pandoc converts a sanitized document AST into HTML, then optional PyMuPDF Story renders it on A4 pages with local font fallback. This route does not require LaTeX. Validate that the resulting document has nonempty readable pages.

Implementation reference: [PyMuPDF Story documentation](https://pymupdf.readthedocs.io/en/latest/story-class.html). Do not equate successful layout with semantic or visual correctness.

Source metadata is removed before rendering; raw active markup and image nodes require a separately reviewed resource workflow and are not rendered automatically. No remote book resources are fetched. Complex tables, mathematics, figures, custom fonts and exact original pagination need review; faithful rich-layout reproduction is not guaranteed.

`export-report.json` records the current edition hash and per-format successes/failures. A failed renderer preserves the old exported file, but that file may be stale; the current report controls its status. Each format is replaced only after its new artifact validates. PDF/EPUB availability depends on actual installed tools; report failures and deliver only successful formats.

## Reader review

Open the generated EPUB/PDF in a compatible reader and inspect beginning/middle/end, chapter order, notes and summaries. Check target-script glyphs, font shaping, code, tables, footnotes and navigation. Font fallback is not proof that every script renders correctly. Keep uncertainty visible and never claim all requested formats succeeded solely because Markdown assembly did.

Current editorial labels are Indonesian for target `id`/`id-*` and English otherwise; translated body content remains in the requested language. Further label localization is not yet implemented.
