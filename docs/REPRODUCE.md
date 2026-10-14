# Reproducibility Record

## Status and paper revision

**Status: TEMPLATE — no research runs, datasets, model weights, or real results recorded.**
Paper revision means the clean checkout containing this record. After committing,
resolve it using `git rev-parse HEAD`. Do not put that same commit's own final hash
inside this tracked file. Generate `build/provenance.json` after committing.

## Direct submodule inventory

The JSON block is maintained by `make record-pins REASON="..."` from the **Git index**.
An empty list means no dependencies have been configured; it is not a successful
experiment-reproducibility check. Review/stage the inventory with the gitlinks.

<!-- pins:start -->
```json
[]
```
<!-- pins:end -->

Nested dependency commits: none configured. Once present, include their full pin
inventory here or reference a committed experiment manifest; release artifacts
also include raw recursive submodule status.

## Manuscript environment

Required Typst version: **0.15.1**, authoritative machine-readable file: `.typst-version`.
Typst packages: **none**. Fonts: compiler-embedded Libertinus Serif and default math
fonts. The compile target ignores system fonts; it fixes PDF creation timestamp to
Unix epoch zero to remove one environmental variable, not to promise bitwise
reproducibility on every machine. Do not add fonts/packages without recording them.

Maintenance scripts: Python 3.10+ standard library, Git 2.28+, GNU Make optional.
Platform-specific native dependency versions must be recorded once introduced.

## Research environment, data, and results

Experiment environment / lockfile: **NOT CONFIGURED**.
Data sources / versioned URLs / SHA-256 / access requirements: **NONE RECORDED**.
Figures / tables / configurations / seeds / actual code version: **NONE RECORDED**.
Scientific numerical tolerances and acceptance criteria: **NOT DEFINED**.

For each real run, add: run ID; experiment and actual code full SHA; environment
lockfile hash or immutable container digest; random seeds; hardware; dataset
version and digest; exact working directory/commands; output SHA-256; tolerances;
known deviations. A new code pin does not relabel old figures as regenerated.

## Commands

```bash
make check
make test
make compile
# After dependency URLs/pins and real hooks have been configured:
make submodules
make check-dependencies
make code-test
make figures
# After a reviewed commit:
make manifest
```

## Validation evidence

Project-specific validation: **NOT RUN**. Replace this statement with commands,
versions, observed results, limitations, and the tested revision as work proceeds.
The bundle-level `VALIDATION.md` describes template assembly tests only, not this
future research project's scientific results or a run in the user's GitHub account.
