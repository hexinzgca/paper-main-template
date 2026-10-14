# Release checklist

No workflow in this starter creates tags or publishes releases automatically.
Release creation requires explicit maintainer approval.

1. Finalize paper content, citations, assets, actual result provenance, environment,
   and direct/nested dependency pins. Replace template text and decide licenses.
2. Commit and review the complete revision. Inspect the diff; check for secrets,
   prohibited artifacts, unpublished dependency commits and untracked work.
3. In a **fresh clone from the real collaborator-facing remote**, check out the
   exact final paper commit, initialize dependencies recursively, verify each pin
   is reachable from the approved upstream branch or retained release tag, and
   run `make check-history`, `make check-dependencies`, `make test`, `make code-test`
   when applicable, and `make compile`. Run the real scientific reproduction
   commands and inspect the PDF, figures and numerical tolerances.
4. Run `make release-manifest`. This records the actual commit and pinned state;
   it does not certify the manual/scientific checks. Attach their evidence too.
5. Only after validation and approval, create an annotated tag on that commit.

```bash
# Run only after completing the gates above.
(
  set -eu
  : "${RELEASE_TAG:?Choose a new approved tag name}"
  PAPER_SHA=$(git rev-parse HEAD)
  git tag -a "$RELEASE_TAG" "$PAPER_SHA" -m "Validated paper snapshot: $PAPER_SHA"
  git show --no-patch "$RELEASE_TAG"
  # Publishing is a separate authorized action:
  # git push origin "$RELEASE_TAG"
)
```

Suggested names: `paper-v1`, `paper-v2`, `paper-submit`, `paper-rebuttal`, `paper-final`.
Never move a published tag or push all local tags blindly.
Publish `build/main.pdf`, `build/provenance.json`, check logs, real environment/data
manifests, and archival references through the approved release process. The
manifest must be generated from the final commit, not before a further edit.
Preserve required dependencies and external research artifacts in suitable archives;
a Git pin alone is not a permanent hosting guarantee.
