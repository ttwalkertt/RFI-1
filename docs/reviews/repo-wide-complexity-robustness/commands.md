# Commands and reproduction

All commands were run from `/Users/tim-macbook/src/RFI-1` on branch `main`.

## Governing context and inventory

```sh
sed -n '1,260p' docs/framework-task-operating-model.md
sed -n '1,260p' TASKS.md
sed -n '1,260p' ARCHITECTURE.md
sed -n '1,240p' DESIGN_PRINCIPLES.md
sed -n '1,240p' ROADMAP.md
sed -n '1,260p' docs/operator-guide.md
sed -n '1,320p' tasks/TASK-065-Require-Explicit-Transcript-Provider-for-Seed-Injection.md
rg --files
git status --short --branch
git log -8 --oneline --decorate
```

The review also read relevant task tickets/reviews and numbered source sections cited in the main
review. Searches used `rg` for compatibility/migration/fallback/exception paths, repository access,
restart/cancellation/concurrency contracts, source identity, and test-private seams. `wc -l`, AST
inspection, and Git file history were used only as supporting evidence.

## Raw metrics

```sh
.venv/bin/python scripts/repo_review_metrics.py \
  --output docs/reviews/repo-wide-complexity-robustness/metrics.json
```

The script uses the Python AST and Git history. It does not calculate a composite complexity score.

## Deterministic probes

```sh
PYTHONPATH=src .venv/bin/python scripts/repo_review_probes.py \
  --output docs/reviews/repo-wide-complexity-robustness/probes.json
```

The probes create only temporary repositories. They perform no network access and do not modify
production code or retained operator state.

## Focused validation

```sh
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_task021 tests.test_task038 tests.test_task056 tests.test_task015 \
  tests.test_task032 tests.test_task064 tests.test_task065 tests.test_review_package -v
```

Three local HTTP tests could not bind an ephemeral loopback port inside the initial sandbox. They
were rerun with loopback binding permitted:

```sh
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_task015.PullInterfaceTests.test_rest_initiates_observes_and_returns_durable_results \
  tests.test_task065.ExplicitProviderApiTests.test_body_provider_is_required_and_query_selection_is_rejected \
  tests.test_task065.PersistedProviderLearningTests.test_endpoint_returns_persisted_provider_unchanged_and_is_read_only -v
```

## Full validation and final checks

```sh
make validate
git diff --check
git status --short --branch
git diff --stat
git diff -- docs/repo-wide-complexity-robustness-review.md \
  docs/reviews/repo-wide-complexity-robustness scripts/repo_review_metrics.py \
  scripts/repo_review_probes.py
```

See `validation.md` for results. The package commit is the commit containing this directory; resolve
it without a self-referential embedded hash using:

```sh
git log -1 --format=%H -- docs/reviews/repo-wide-complexity-robustness
```
