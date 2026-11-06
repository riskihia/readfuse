# ReadFuse development and releases

## Branch responsibilities

- `dev`: source development, tests, examples, and design/implementation records.
- `main`: the user-facing skill package. Keep only `.gitignore`, `LICENSE`, `README.md`, `SKILL.md`, `assets/`, `references/`, and runtime helpers under `scripts/`.

Private books, local jobs, local dependencies, and agent scratch state remain ignored on both branches. Ignored directories may still exist in your local checkout when you switch branches; their presence does not put them in GitHub's main tree.

Both branches share the runtime implementation. Develop runtime changes on `dev`, then copy reviewed runtime paths to `main`. Do not merge all of `dev` into `main`: that would restore development-only directories. Do not merge the packaging-removal commit from `main` into `dev`, because it would delete the development files there.

## Development checks

Work on `dev` or a feature branch created from it:

```bash
git switch dev
git switch -c feature/my-change
python -m unittest discover -s tests -v
python scripts/readfuse_cli.py --help
```

Optional PDF/export checks require PyMuPDF and Pandoc. Install them in your Python environment. In the original workspace, `.readfuse-deps` contains optional dependencies; set `PYTHONPATH` to its absolute path when using that local installation. Windows symlink tests may require additional privileges. Semantic fixtures do not certify translation quality for all books or languages.

The original sample workflow and artifacts are in `examples/learning-edition/` and `tests/fixtures/learning-book.md` on `dev`. User-book jobs must remain private and ignored.

## Update main after a reviewed development change

First commit and review the change on `dev`. With a clean working tree, update only the runtime paths on `main`:

```bash
git switch main
git restore --source=dev -- .gitignore LICENSE README.md SKILL.md assets references scripts/readfuse scripts/readfuse_cli.py scripts/checkpoint.py
git diff --check
git diff --stat
git ls-files
git add .gitignore LICENSE README.md SKILL.md assets references scripts/readfuse scripts/readfuse_cli.py scripts/checkpoint.py
git commit -m "release: update ReadFuse skill"
```

Review the diff before committing. Keep README user-facing on both branches, and keep development instructions in this document. If a new runtime file is introduced, deliberately add its path to the release list. Before publishing, confirm that main tracks no `tests/`, `docs/`, `examples/`, local book/job, environment, or scratch files. Validate the skill and inspect the CLI help from the main package.

Copying paths is an intentional release snapshot, so main and dev histories diverge. Compare runtime paths when reviewing releases rather than relying on branch merge status. Tag releases on main if desired. Pushing, adding a remote, and publishing are separate actions.

## Public repository visibility

Set `main` as the repository's default branch when creating the GitHub repository. Anyone can still browse `dev` if it is pushed to a public repository. Removing development directories from the latest main tree does not erase them from earlier Git history. Never use this branch separation as a way to hide secrets or private books.
