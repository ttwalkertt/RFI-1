# TASK-050 Review

## Outcome

Review-package evidence is now bound to an explicit committed implementation range. The shared
builder resolves the review base independently of branch upstream, records base, head, merge base,
range, branch, clean status, and upstream divergence, and generates its patch, file inventory, and
statistics exclusively from that range.

Dirty generation fails by default. An explicit library argument is required to retain the narrower
diagnostic capability, and dirty state is never substituted into the committed implementation
patch.

## Package Contract and Verification

Format version 2 separates implementation identity from package-generation metadata. Each package
contains committed patch and comparison evidence plus a finalized manifest of every payload member.
The staging directory is rebuilt from nothing before every generation.

Independent verification opens an existing ZIP without regeneration and checks:

- ZIP CRC integrity and one matching task root;
- explicit format and package identity;
- required members and exact manifest completeness;
- every member's SHA-256 digest and byte count;
- base, head, merge-base, and range agreement across metadata;
- patch, changed-file inventory, and numstat file-set agreement.

## Validation

Focused tests exercise clean committed generation, exact commit/base/range capture, non-empty patch
evidence, changed-file and statistics consistency, clean status, upstream divergence, dirty-tree
policy, repeated deterministic output, stale staging removal, valid verification, corrupted member
detection, and semantic inconsistency detection after an attacker updates a member hash.

The generated package includes focused-test, `git diff --check`, and full `make validate`
transcripts, along with an external SHA-256 and ZIP integrity report.

## Limitations

- The default base assumes the repository exposes a remote default branch through `origin/HEAD`,
  with conventional main/master fallbacks; unusual repositories must pass an explicit base.
- Format version 2 deliberately uses no-renames comparison so patch and file inventory have a
  simple, independently verifiable one-path-per-change contract.
- The task changes package generation and verification only; it does not alter validation commands,
  commit workflow, ZIP format, or review policy.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Review identity resolution | Bind evidence to deterministic committed base, head, merge base, and range | Complete |
| Repository-state capture | Record branch, clean status, and upstream divergence separately | Complete |
| Committed comparison evidence | Produce patch, changed files, diff statistics, and numstat from one range | Complete |
| Package staging and manifest | Rebuild all members, then finalize versioned hashes and sizes | Complete |
| Independent verification | Validate an existing ZIP's integrity, identity, membership, and consistency | Complete |
| Task-specific review narratives | Supply completed-state content to the shared package builder | Usable with limitations |

Architectural change: implementation identity, repository state, and generation time are now
separate first-class records. The remaining limitation is that task-specific wrappers still choose
their narrative and validation artifacts. The next architectural milestone can reuse this shared
contract rather than recreating Git evidence and verification logic.
