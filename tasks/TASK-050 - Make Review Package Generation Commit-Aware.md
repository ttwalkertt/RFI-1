# TASK-050 --- Make Review Package Generation Commit-Aware

## Status

Complete

------------------------------------------------------------------------

## Objective

Correct the review-package generator so that review packages generated
after the project's normal commit-and-push workflow accurately represent
the committed implementation rather than the transient working tree.

This task modifies only review-package generation and verification. It
shall not modify implementation behavior, validation execution, Git
workflow, repository state, or review policy.

------------------------------------------------------------------------

## Background

The current review generator assumes the implementation exists as
uncommitted working-tree changes.

After the project's standard workflow:

-   implementation committed;
-   branch pushed;
-   working tree clean;

the generator incorrectly records:

-   an empty implementation patch;
-   repository metadata bound to the wrong commit;
-   stale working-tree status;
-   stale review summaries captured before completion.

TASK-048B required manual correction of ignored review artifacts to
produce an accurate review package.

The generator shall instead produce correct review evidence directly
from the committed implementation.

------------------------------------------------------------------------

## In Scope

-   Generate implementation patches from the committed review range when
    the working tree is clean.
-   Record the reviewed implementation commit.
-   Record the review base commit.
-   Record the resolved review range.
-   Record branch synchronization status.
-   Record clean Git status.
-   Generate the changed-file inventory from the committed comparison.
-   Ensure repository metadata always reflects the reviewed
    implementation.
-   Ensure review summaries represent the completed implementation
    state.
-   Preserve manifest generation and ZIP verification.

## Out of Scope

Do not modify review package layout, philosophy, validation execution,
Git workflow, commit policy, production recovery workflow, task
workflow, or ZIP format.

## Required Behavior

### Clean committed repository

When generating a package from a committed implementation with a clean
working tree, the generator shall:

-   determine the reviewed implementation commit;
-   determine the deterministic review base;
-   generate the implementation patch from the committed review range;
-   never substitute a working-tree diff for the implementation patch;
-   record the reviewed commit;
-   record the review base;
-   record the review range;
-   record clean Git status;
-   record upstream divergence;
-   record the committed changed-file inventory.

### Dirty working tree

By default, review generation shall fail on a dirty working tree. Dirty
working-tree generation, if retained, shall require explicit operator
intent.

## Required Invariants

### Commit identity

The package shall explicitly identify:

-   reviewed base commit;
-   reviewed head commit;
-   merge base (if used);
-   resolved review range.

### Patch correctness

The implementation patch shall:

-   correspond exactly to the reviewed implementation;
-   never be empty when the committed review range is non-empty;
-   match the changed-file inventory;
-   match the recorded review range.

### Repository metadata

Repository metadata shall accurately record:

-   reviewed implementation commit;
-   generation timestamp;
-   branch name;
-   Git status;
-   upstream divergence.

Implementation identity and package-generation state shall remain
separate concepts.

### Determinism

Generating the review package repeatedly from identical repository state
shall produce identical package contents except for intentionally
variable metadata such as timestamps.

### Package staging

Generation shall:

1.  remove any previous staging directory;
2.  rebuild every package member;
3.  generate the manifest only after all members are finalized;
4.  build the ZIP;
5.  verify ZIP integrity against the manifest.

### Package verification

Provide an independent package verification mode capable of validating
an existing package without regenerating it.

Verification shall include:

-   required members;
-   manifest completeness;
-   member hashes;
-   ZIP integrity;
-   patch/file-list consistency;
-   review-range metadata;
-   package identity.

### Package versioning

Introduce explicit review-package format version metadata.

## Regression Tests

Add focused coverage proving:

1.  clean committed branch produces a non-empty committed implementation
    patch;
2.  reviewed commit matches the committed implementation;
3.  reviewed base and review range are recorded correctly;
4.  changed-file inventory matches the committed comparison;
5.  patch, diff statistics, and changed-file inventory are mutually
    consistent;
6.  clean worktree records clean status;
7.  upstream divergence is recorded correctly;
8.  dirty working-tree generation follows the documented policy;
9.  repeated generation is deterministic;
10. stale staging artifacts cannot survive regeneration;
11. package verification succeeds on a valid package;
12. package verification detects corrupted members;
13. manifest verification continues to pass;
14. ZIP integrity continues to pass.

## Validation

Run:

-   focused review-package tests;
-   package verification tests;
-   manifest verification;
-   ZIP integrity verification;
-   full `make validate`.

Generate a fresh review package from a clean committed branch and
verify:

-   implementation patch is populated;
-   reviewed commit is correct;
-   review range is correct;
-   changed-file inventory is correct;
-   Git status is clean;
-   upstream divergence is correct;
-   package verification passes;
-   manifest verification passes;
-   ZIP integrity passes.

## Architectural Review

A review package is evidence of a specific committed implementation, not
a snapshot of transient repository state.

The package shall therefore be commit-aware whenever a committed
implementation exists.

Implementation identity, review range, repository state, and
package-generation state are distinct concepts and shall be represented
independently.

Review packages must remain deterministic, reproducible,
self-consistent, and independently verifiable.

## Completion Evidence

Provide:

-   complete review package;
-   package verification report;
-   manifest verification;
-   ZIP integrity report;
-   committed review range;
-   reviewed base commit;
-   reviewed head commit;
-   package format version;
-   final validation summary.

------------------------------------------------------------------------

## Completion Record

Implemented by the shared `scripts/review_package.py` package builder and verifier, with
`scripts/generate_task050_review.py` as the current operator entry point. The builder resolves the
remote default branch (or an explicit base), records its merge base with `HEAD`, and derives the
patch, changed-file inventory, human-readable statistics, and machine-checkable numstat from that
committed range. Generation rejects dirty trees by default; the library exposes dirty generation
only through explicit caller intent.

The independently callable `--verify` mode validates ZIP CRCs, required members, complete manifest
membership, hashes and sizes, package identity, range metadata, and patch/file/stat consistency
without rebuilding the package. Format version 2 makes the contract explicit. Staging is deleted
before every build, and the manifest is written only after every payload member is finalized.

Focused tests cover clean committed generation, commit/base/range identity, changed files and
statistics, clean status, upstream divergence, dirty policy, deterministic repeated generation,
stale staging removal, valid verification, member corruption, and internally rehashed inventory
corruption. The final package records the exact committed review range and the complete validation
transcripts.
