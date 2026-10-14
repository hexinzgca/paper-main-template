# AGENTS.md — Typst Paper Project Maintainer Specification

> Instructions for AI agents working on `paper-main` and its pinned dependencies.
> Keep the paper introduction and contributor quick start in `README.md`.
> This specification defines required behavior; it does not imply that the described
> scripts, CI checks, credentials, or local editor settings already exist.

## 0. Template-specific implementation status

This is a starter, not a completed research project. Read `docs/TEMPLATE_STATUS.md`
for the implemented checks and remaining human/project-specific gates.

- `project.json` stores manuscript metadata. The one-time `init` command changes
  only this file; it never creates repositories, commits, tags, or remotes.
- Empty `.gitmodules` and an empty pin inventory are intentional until approved
  code and experiment repositories exist. Do not invent gitlinks or hashes.
- `make check` validates the Git index. Stage intended tracked changes first; it
  fails on unstaged tracked changes rather than certifying a different snapshot.
  It does not rewrite files or silently initialize dependencies.
- `make record-pins REASON="..."` explicitly updates the marked JSON inventory
  inside `docs/REPRODUCE.md` from staged gitlinks. It preserves the surrounding
  narrative. Review and stage the record with the pin changes.
- `make check-history` additionally checks reachable committed blob sizes. Use a
  full `BASE_REV` for a PR range; the default is the entire history reachable from
  HEAD. This supplements staged checks and catches oversized files later deleted.
- `make check-dependencies` requires initialized pins when dependencies exist.
  A template with no dependencies is NOT evidence of experiment reproducibility.
- `config/hooks.json` documents the owning repositories' test/figure argv arrays.
  The supplied companion seeds implement `make test`; their figure command is
  intentionally BLOCKED until the project's real rendering pipeline is added.
- Direct mount paths use `submodules/<name>` with a simple ASCII name. The
  bootstrap template accepts absolute HTTPS/SSH URLs without credentials, and
  rejects executable/non-checkout update settings and hidden submodule status.
  Adopt any broader URL/topology policy only as an explicit reviewed change.
- The default CI is unprivileged and public-dependency oriented. Private access,
  trusted upstream-ref selection, standalone research validation, and Tylina
  exclusions remain explicitly configured or manual gates.

## 1. Scope and operating contract

Maintain three independent repositories: `paper-main` for the manuscript,
`paper-code` for reusable software, and `paper-experiments` for experimental
workflows. The latter two are mounted as Git submodules. Preserve independent
history, explicit version selection, and traceable paper results.

**MUST** and **MUST NOT** are mandatory. **SHOULD** requires a documented reason
for deviation. Examples are instructions for an authorized task, not standing
permission to publish, delete, or change unrelated repositories.

- Follow the active task and higher-priority agent instructions. Apply this file
  to `paper-main`; read each submodule's own instructions before working there.
- Keep changes minimal and task-scoped. Do not redesign the repository, change
  scientific claims, invent results or citations, or alter experiment settings
  merely to make checks pass.
- Inspect existing edits before changing files or Git state. Preserve unrelated
  work, including staged changes and untracked files. Do not automatically stash,
  reset, clean, force-checkout, or resolve conflicts by discarding either side.
- Do not commit, push, open or merge a PR, create a release tag, or change remotes
  unless the task or an explicitly configured automation authorizes that action.
- Never force-push shared history, move published release tags, expose credentials,
  or silently bypass required checks.
- Report checks as **PASS**, **FAIL**, **BLOCKED**, or **NOT RUN**, with evidence.
  Missing tools, permissions, data, or local settings are not successful validation.

## 2. Repository architecture and content boundaries

```text
paper-main/
├── AGENTS.md                 # Agent maintenance policy
├── README.md                # Paper overview and contributor quick start
├── .github/                 # CI workflows and issue/PR templates
├── src/
│   ├── main.typ             # Manuscript entry point
│   ├── sections/            # Manuscript sections
│   ├── figs/                # Optional Typst-native figure/layout definitions
│   └── refs.bib             # Bibliography
├── assets/                  # Final rendered figures and small static artwork
├── docs/
│   └── REPRODUCE.md          # Dependency, environment, data, and figure provenance
├── submodules/
│   ├── code/                # Independent paper-code repository
│   └── experiments/         # Independent paper-experiments repository
├── build/                   # Generated outputs; ignored by Git
├── Makefile                 # Or justfile; one authoritative command interface
├── .gitmodules              # Submodule paths and repository URLs
└── .gitignore
```

| Location | Permitted content | Excluded content |
| --- | --- | --- |
| `paper-main` | Typst sources, bibliography, final figures, documentation, lightweight build/CI tooling, submodule gitlinks | Raw datasets, model weights, raw training logs, copied implementations from submodules |
| `submodules/code` | Reusable source code, tests, environment definitions, algorithm configs, lightweight plotting utilities | Manuscript content, raw datasets, weights, large output artifacts |
| `submodules/experiments` | Experiment configs, metric summaries, analysis and plotting scripts, artifact manifests | Raw datasets, weights, large raw logs |

All direct submodules MUST live under `submodules/`. The parent tracks each
submodule as a **gitlink** containing a commit ID, not an empty directory or its
individual source files. Dependencies inside a submodule remain that repository's
responsibility. [1, 2]

Dependencies MUST be one-way: `paper-main` consumes code and experiments; neither
submodule may require `paper-main` to build, test, or run. A citation or README link
back to the paper is not a dependency. Experiments may consume the code repository,
but MUST declare its version and remain runnable outside this parent checkout.
If that declared version differs from the paper's code pin, document the reason
and the code version actually used to generate each result.

### Artifact limits

- Static assets SHOULD be smaller than **2 MB**. Assets from 2 MB through 10 MB
  require a recorded justification. Here, MB means 1,000,000 bytes.
- No ordinary Git file blob larger than **10 MB** may be introduced into
  `paper-main`. Apply the subrepositories' own documented size limits there.
- Store large research artifacts externally, such as Zenodo, OSF, or object
  storage. Record the versioned location and SHA-256 checksum. Never commit
  credentials or temporary signed download URLs.
- Git LFS or DVC may be adopted explicitly, with retrieval and CI support
  documented first. They are not an exception to the exclusions above.
- Keep compiled PDFs and temporary outputs under `build/` or another documented,
  ignored output directory. Publish them as CI or release artifacts by default.

## 3. Start-of-task checks and command interface

Read `README.md`, `docs/REPRODUCE.md`, `.gitmodules`, and the existing build/CI
configuration before relying on them. Missing files are setup gaps, not evidence
that the documented behavior is implemented.

From the parent repository root, inspect:

```bash
git rev-parse --show-toplevel
git status --short --branch --untracked-files=all --ignore-submodules=none
git diff --submodule=log
git diff --cached --submodule=log
git submodule status --recursive
```

For submodule operations, inspect that repository and any initialized nested
submodules for local edits and unpublished work as well. Stop the affected
operation if it would disturb existing work; unrelated safe edits may continue.

Use one command vocabulary throughout README, CI, and reproducibility records:

| Command | Contract |
| --- | --- |
| `make compile` | Compile the manuscript using committed final assets; do not run experiments or change submodule pins. |
| `make submodules` | Initialize/check out recorded pins with `--init --recursive --checkout`; never follow remote branch tips. |
| `make check` | Run implemented lightweight validation without rewriting tracked files, changing pins, or committing. |
| `make figures` | Run documented figure-generation commands with pinned inputs; no full training by default. |

These are the normalized target names for this specification. Inspect the actual
Makefile before invocation. If only a justfile exists, use documented equivalent
recipes. Do not introduce a second build interface or rename existing targets
outside an authorized setup change. Report missing targets rather than inventing
successful command results.

The manuscript compilation contract is equivalent to:

```bash
mkdir -p build
typst compile --root . src/main.typ build/main.pdf
```

Record the tested Typst version, package versions, and required fonts in
`docs/REPRODUCE.md`. Do not silently upgrade them. A manuscript-only build MUST
not require submodule files, raw data, or training; required packages and fonts
must still be installed or obtainable through the documented setup.

## 4. Git submodule lifecycle

Shell examples assume Bash (including Git Bash on Windows). Run each step only
after its preconditions are satisfied, and stop immediately on a nonzero exit.

### 4.1 Fixed-pin invariant

The committed gitlink is the authoritative pin. Record **full commit hashes** in
provenance; branch names, tag names, and abbreviated hashes are not substitutes.
A detached HEAD is expected for a checked-out dependency. [1, 2]

Do not add a `.gitmodules` `branch` field merely to document the pin: that field
configures remote-branch updates and is not informational metadata. An existing
field does not invalidate a gitlink pin, but does not authorize following it. [3]

**Never run `git submodule update --remote` or use `git pull` inside a pinned
submodule as the parent repository's upgrade procedure.**

### 4.2 Bootstrap and restore recorded pins

For a new checkout of an approved repository:

```bash
# PAPER_URL must be the approved parent-repository URL.
: "${PAPER_URL:?Set the approved parent-repository URL}"
git clone --recurse-submodules "$PAPER_URL" paper-main
```

For an existing checkout, after reviewing repository URLs and local state:

```bash
git submodule update --init --recursive --checkout
git submodule status --recursive
```

Use the same update command after switching the parent branch. Do not run it in
the middle of an intentional, not-yet-staged pin change: it restores the pin
currently recorded in the parent index. [1]

If `.gitmodules` URLs changed, review the change and any local URL overrides
before running `git submodule sync --recursive`, then restore recorded pins.
Never overwrite a collaborator's intentional local remote configuration blindly.

A leading `-`, `+`, or `U` in submodule status means uninitialized, mismatched,
or conflicted state, respectively. Resolve or report it; do not hide it. [1]

### 4.3 Upgrade an explicitly selected commit

Preconditions: the target submodule and its nested worktrees are clean; the target
commit is approved, available from the configured upstream, and any required
upstream PR is merged. Verify remote availability as described in Section 4.4.

Example for `code`; apply the same procedure to `experiments`:

```bash
# Run from paper-main. TARGET_SHA must be the approved full commit hash.
(
  set -eu
  : "${TARGET_SHA:?Set the approved full commit hash}"
  git -C submodules/code fetch origin
  RESOLVED_SHA=$(git -C submodules/code rev-parse --verify --end-of-options "$TARGET_SHA^{commit}")
  if [ "$RESOLVED_SHA" != "$TARGET_SHA" ]; then
    printf '%s\n' 'STOP: target must resolve to the exact full commit hash.' >&2
    exit 1
  fi
  git -C submodules/code checkout --detach "$TARGET_SHA"
  git -C submodules/code submodule update --init --recursive --checkout
  git diff --submodule=log -- submodules/code
)
```

Stop on any command failure. Inspect the upstream diff and test requirements.
Update `docs/REPRODUCE.md`, including the reason for the change and any affected
figures or results. Changing a pin alone does not establish that old results were
regenerated with the new code.

Then stage the pin and its provenance together:

```bash
git add -- submodules/code docs/REPRODUCE.md
git ls-files --stage -- submodules/code
git diff --cached --submodule=log
git diff --cached --check
```

Verify mode `160000` and the intended commit hash in the staged entry. Run the
required checks. Only then, if authorized, create the parent commit and PR. Do not
commit the pointer first and leave its reproducibility record for a later commit.

### 4.4 Verify remote availability

A commit existing in the current local clone is insufficient. In CI or a disposable
checkout, fetch/clone from the URL collaborators will use, without relying on local
object caches or alternates. Verify that the exact commit is available and reachable
from the approved upstream branch or retained release tag, then check it out.
Account for nested submodules and access permissions.

Do not validate arbitrary historical commits by searching `git ls-remote` output
for the hash: that command lists advertised refs, not every reachable commit. [4]
A clean recursive checkout of the proposed parent revision is required for release
validation. Access or network failures are **BLOCKED**, not proof that the commit
is absent and not a passing check. Pinning does not guarantee permanent hosting;
formal releases SHOULD also preserve an archival copy of required dependencies.

### 4.5 Source changes inside a submodule

Parent-maintenance tasks treat submodule sources as read-only. When the active
task explicitly includes a code or experiment change, work under that repository's
rules, preferably in a separate checkout and on its own development branch.
Local debugging inside a mounted submodule is allowed only within that scope.

Commit and review source changes in the owning repository. Publish and merge them
there first; then update the parent pin to the **actual approved upstream commit**
using Section 4.3. Do not pin unpublished local commits or an obsolete pre-squash
PR commit. Never copy the implementation into `paper-main` as a workaround.

### 4.6 Add or remove a submodule

Require explicit authorization for topology changes. Validate the repository URL,
license/access requirements, standalone behavior, and destination first.

```bash
# CODE_URL must be approved; the destination must not already contain work.
: "${CODE_URL:?Set the approved code-repository URL}"
git submodule add --name code "$CODE_URL" submodules/code
```

For `experiments`, use its approved URL, name, and path. Select and verify an
explicit full commit, including nested pins, before final staging. Stage
`.gitmodules`, the gitlink, and `docs/REPRODUCE.md` together. Do not use `-b` as a
substitute for selecting a commit.

To remove `code`, first preserve local work and confirm required commits have
been published or backed up:

```bash
git submodule deinit -- submodules/code
git rm -- submodules/code
```

Review the resulting `.gitmodules` change and update provenance, build targets,
and documentation in the same change. Git normally retains the module's Git
directory to support older revisions. **Do not routinely delete `.git/modules/`
or use `rm -rf` as part of removal.** Cache deletion is a separate, explicitly
authorized maintenance operation after verifying its actual path and backups. [2]

## 5. Figure workflow and Typst paths

Generate figures with the pinned experiment scripts and documented inputs. Record
the experiment commit, code version actually used, configuration/run identifier,
data checksums, command, and output SHA-256 in `docs/REPRODUCE.md` or a referenced
manifest committed in the experiments repository.

Render to a documented ignored output directory. Copy **only the final artifact**
into `assets/`; retain plotting source in the owning repository. Inspect the figure
and diff before staging it. Do not hand-edit scientific values in exported images.

From manuscript files, use a path relative to the configured project root:

```typst
#image("/assets/fig4.svg")
```

This requires the repository-root build configuration in Section 3. A plain
`image("assets/fig4.svg")` inside `src/main.typ` would resolve relative to `src/`,
not automatically to the repository root. Do not reference or symlink final assets
from `submodules/` into the manuscript. [5]

## 6. Tylina and file synchronization

Tylina remains the designated manuscript editor/synchronization workflow in the
project design. Git remains the authority for version history and submodule pins.
**Do not assume a particular Tylina version exposes a specific ignore-file format,
configuration path, or programmable settings interface.**

Before enabling file synchronization on `paper-main`, verify that the actual sync
mechanism excludes at least these paths and their contents:

```text
.git/
submodules/
build/
```

These are required exclusions, not a ready-to-use Tylina configuration file.
Do not add `submodules/` to `.gitignore` to achieve this: Git must track the gitlinks.
Exclude Git metadata even when `.git` is a file, as in a linked worktree; do not
follow symlinks into excluded directories.

Inspect only configuration that is available and within the authorized scope.
Record a manual verification requirement when local settings cannot be inspected.
If exclusion support is unknown or absent, do not enable whole-repository file
sync; use Git for transfers until a safe setup is confirmed. CI cannot certify
settings on a collaborator's device. Pause concurrent editor/sync writes during
branch switches and release preparation, then re-check Git status.

## 7. Reproducibility records and release snapshots

Update `docs/REPRODUCE.md` whenever a submodule is added, removed, or repinned, or
when a figure, dataset version, experiment configuration, or build environment
changes. Record full hashes and verified values, not plausible placeholders.

Minimum record template:

```text
Paper revision: the clean checkout containing this record
Resolve paper commit: git rev-parse HEAD
Code: <repository URL>, <full pinned commit hash>
Experiments: <repository URL>, <full pinned commit hash>
Nested dependencies: <full pin inventory, or none>
Build environment: <Typst version, package versions, font requirements>
Experiment environment: <lockfile path/hash or immutable container digest>
Data: <versioned URL/archive identifier>, sha256=<digest>, <access requirements>
Results: <figure/table>, <run/config>, <actual code hash>, <input/output digests>
Reproduction: <exact commands, working directories, and required resources>
Validation: <checks run, results, limitations, numerical tolerances if applicable>
```

Do not try to store a commit's own final hash inside a file that is part of that
same commit. Resolve the paper hash after committing; include it in the release
annotation and/or an untracked generated provenance artifact. A parent or earlier
commit hash must never be mislabeled as the current paper revision.

### Release sequence

1. Finalize manuscript content, assets, dependency pins, and reproducibility
   records. Commit them together as appropriate and complete review.
2. Validate the exact final commit in a clean checkout, including recursive
   submodule availability, manuscript build, and required lightweight tests.
3. If release creation is authorized, create an **annotated tag** on that validated
   commit. Never tag first and update the tagged record afterward. [6]
4. Generate the release provenance artifact from that commit, recording its full
   hash and all direct/nested pins. Include environment and external artifact
   references. Attach it with the compiled paper when publishing is authorized.
5. Push only the explicitly approved branch/tag. Never use a blanket tag push or
   replace an already published tag.

Preserve the naming scheme: `paper-v1`, `paper-v2`, `paper-submit`,
`paper-rebuttal`, and `paper-final`. For another snapshot, choose a new approved
name rather than reusing a published one. During review, keep the frozen snapshot
unchanged; develop new code/experiments independently and repin only for an
explicitly approved subsequent paper revision.

## 8. Commit messages and pull requests

Use `type(scope): description`, with scope optional.

| Repository | Allowed types |
| --- | --- |
| `paper-main` | `typst`, `ref`, `fig`, `submodule`, `docs`, `ci`, `meta` |
| Code/experiments | Follow their own policy; baseline types are `feat`, `fix`, `exp`, `plot`, `ci` |

```text
typst: clarify section 3.2 convergence assumptions
fig: update figure 4 from the recorded ablation run
submodule(code): pin reviewed solver update
docs: record submission reproduction environment
```

Put full old/new hashes and the reason for a pin change in the commit body or PR,
with the new hash also in `docs/REPRODUCE.md`. Configure commitlint to allow these
custom types before claiming enforcement; its default rules are not this policy.

A PR description MUST identify changed repositories/files, motivation, upstream
PRs and old/new pins when applicable, affected results, provenance updates, and
check results. Do not include unrelated formatting or generated build outputs.

## 9. CI, review gates, and completion criteria

This is the required validation contract, not a claim that CI already implements
it. A required check that cannot run is **BLOCKED**; an optional skipped check is
**NOT RUN** with a reason.

| Check | Required evidence |
| --- | --- |
| Submodule integrity | `.gitmodules` matches the gitlinks; approved paths/URLs; exact pins retrievable; no uninitialized, mismatched, dirty, or conflicted dependencies in the validation checkout. |
| Provenance | Recorded pins equal the proposed commit's gitlinks; changed inputs/results have updated records. Check content, not merely whether the file was touched. |
| Content and size | No prohibited content; no oversized ordinary Git blobs introduced anywhere in the PR's commit range, including files later deleted. Check staged blobs locally, not `.git/` disk usage. |
| Manuscript build | `make compile` succeeds and produces a nonempty PDF; inspect changed equations, references, and figure placement. |
| Lightweight tests | Run the owning code repository's documented tests at the pinned commit. Do not guess a test command. |
| Figure regeneration | Manual/explicitly triggered by default; use recorded inputs and comparison tolerances. Do not run full training in routine CI. |
| Standalone boundaries | Inspect dependency/build configs and, where feasible, test subrepositories without `paper-main`. Text searches alone do not prove absence of circular dependencies. |
| Tylina exclusions | Local/manual verification unless an actual inspectable configuration exists; do not present a reminder as a CI-enforced guarantee. |

Full bootstrap and CI dependency jobs MUST initialize submodules recursively at
the recorded commits. Configure private-repository access explicitly and report
missing permissions. Run untrusted PR code only in an appropriately isolated,
unprivileged job without publishing credentials or secrets. Upload the compiled
PDF and validation logs as CI artifacts; do not commit them back automatically.

Before finishing, inspect the final diff and repository status. Confirm that
required source, pin, and provenance changes are included; check for accidental
submodule dirtiness, secrets, and generated files. Report what changed, the exact
checks executed, failures or blockers, and whether anything was committed or
published. Never claim end-to-end reproducibility from compilation alone.

## 10. Bootstrap and architecture decisions

For an explicitly requested new setup, establish the three repositories, mount
approved submodules at fixed commits, implement the command interface, add the
reproducibility record and CI gates, and verify local synchronization exclusions.
Do not create repositories, choose organization URLs, or configure credentials
without authorization.

Keep the chosen submodule architecture. Subtree or monorepo migration requires a
separate design decision because it changes repository/history boundaries; neither
is prohibited by Git itself. DVC remains an optional artifact-management layer,
not a replacement for pinned source commits.

## Appendix — Adoption notes and technical basis

This revision retains the supplied three-repository architecture and terminology.
The following are deliberate operational clarifications, not observations about
an existing checkout: unified build targets; `build/` as ignored output; a uniform
10 MB parent-blob ceiling; explicit authorization and dirty-worktree guards;
read-only submodules by default with scoped development allowed; atomic
pin/provenance updates; and post-commit release identification.

**Agent discovery:** This template uses `AGENTS.md` as the authoritative entry
file. Do not maintain a divergent `AGENT.md` copy. Agents with other discovery
mechanisms must be configured to read this policy explicitly. [7]

**Unverified local integration:** The supplied material does not establish the
installed Tylina version, ignore syntax, or access to device settings. Public
Tylina documentation reviewed identifies the editor, but does not establish those
local capabilities. Section 6 therefore states required behavior conditionally
rather than inventing a configuration mechanism. [8]

Technical references checked for this revision (2026-10-14):

[1] Git submodule operations: `https://git-scm.com/docs/git-submodule`

[2] Gitlinks, repository boundaries, and removal:
`https://git-scm.com/docs/gitsubmodules`

[3] `.gitmodules` configuration: `https://git-scm.com/docs/gitmodules`

[4] Advertised remote refs: `https://git-scm.com/docs/git-ls-remote`

[5] Typst paths and project roots:
`https://typst.app/docs/reference/foundations/path/`

[6] Annotated tags: `https://git-scm.com/docs/git-tag`

[7] Codex instruction discovery:
`https://developers.openai.com/codex/guides/agents-md`

[8] Tylina public website repository:
`https://github.com/tylina/tylina.github.io`
