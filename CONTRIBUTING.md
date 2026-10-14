# Contributing

Read `AGENTS.md`, `README.md`, and `docs/REPRODUCE.md` before changing the project.
Use a task-scoped branch, inspect existing changes, and preserve unrelated work.
The parent repository owns manuscript files and dependency pointers; source changes
belong in each independent code/experiment repository.

Commit form: `type(scope): description`, scope optional. Parent types:
`typst`, `ref`, `fig`, `submodule`, `docs`, `ci`, `meta`.
Full old/new dependency hashes and upstream review links belong in the commit body
or PR, with new pins also recorded in REPRODUCE.md. No commitlint enforcement is
installed by default.

Before a PR, stage the intended changes, run `make check`, `make test`,
`make compile`, and any dependency/result checks affected by the change.
Inspect generated PDF pages. Record PASS / FAIL / BLOCKED / NOT RUN and evidence.
Do not change scientific claims or omit required checks just to obtain a green job.

Never include secrets, raw datasets, model weights, generated PDFs, or unrelated
formatting changes. Do not push, tag, publish, or rewrite shared history without
explicit authorization. See `docs/RELEASE.md` for release gates.
