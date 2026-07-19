# TASK-024 — Pull-result configuration repair navigation

## Architectural objective

Connect operator-visible pull configuration failures to the existing firm source-profile editor
without introducing another editing surface or weakening pull/source-profile authority boundaries.

## Boundaries and invariants

- Only artifact outcomes equal to `configuration_problem` with both a `firm_id` and canonical
  `artifact_id` are actionable.
- Actionable results navigate in the current tab with an ordinary link. No popup, modal, new tab,
  history replacement, or scripted return path is allowed.
- The URL carries `firm_id` and `artifact_id`; remembered browser preferences remain a fallback,
  not an override of explicit URL identity.
- The source-profile page selects the requested firm, opens the target artifact and parent
  category, scrolls it into view, and provides visible/focus indication.
- Unknown or stale URL identity fails safely. It must not select an artifact for a different firm,
  write a source profile, initiate a pull, or alter domain persistence.
- All other outcome rendering and behavior remains unchanged.
- Pull results remain a read projection of the durable workflow. Source-profile editing remains
  the only configuration-authority surface.

## Acceptance criteria

1. An actionable `configuration_problem` status is a same-tab link to `/source-profiles`.
2. The link query contains the exact result `firm_id` and `artifact_id` with URL encoding.
3. No link uses `target`, `window.open`, a modal, or history replacement.
4. The source-profile page gives a valid URL firm precedence over remembered firm context.
5. The requested artifact and its containing category are open, scrolled into view, focused, and
   visibly identified.
6. A completed run has a durable-result history URL, and browser Back returns through the ordinary
   history entry to the rehydratable pull results.
7. Non-configuration outcomes and configuration outcomes missing identity remain non-links.
8. Unknown firm/artifact parameters fail safely and do not cause writes or pulls.
9. Focused browser and REST/API tests cover identity, routing, selection/reveal, Back, negative
   status behavior, and safe invalid identity behavior.
10. Full repository validation passes and a reproducible review package records implementation,
    validation, browser proof, limitations, and architectural status.

## Required evidence

- focused automated browser harness output;
- focused REST/API output proving pull-result identities;
- real browser proof for current-tab navigation, URL identity, reveal/focus, and Back;
- regression and full validation outputs;
- repository diff/status and exact validation commands;
- sensitive-output scan and review-package ZIP integrity;
- Architectural Status Summary.

## Completion record

Completed 2026-07-19.

- Pull results render identity-bearing `configuration_problem` outcomes as ordinary current-tab
  links and leave all other outcomes as badges.
- Completed runs receive rehydratable `run_id` history URLs, allowing native Back to restore the
  exact durable pull result.
- Source Profiles gives valid URL firm identity precedence over remembered context, then opens,
  scrolls to, highlights, and focuses the canonical artifact.
- Focused browser/API tests, pull/source-profile regressions, the complete project suite, isolated
  copied-tree checks, and real in-app-browser navigation/Back proof pass.
- Review directory: `.artifacts/review/TASK-024`.
- Review archive and checksum: `.artifacts/review/TASK-024-review.zip` and
  `.artifacts/review/TASK-024-review.zip.sha256`.

Known limitation: repair always opens the firm's current editable profile, not the historical
snapshot used by the completed pull. This is intentional because historical revisions are
inspect-only; the result retains its snapshot revision for audit context.

### Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Pull result projection | Show terminal outcomes and route actionable configuration repair | Complete |
| Pull history projection | Rehydrate durable completed results after browser Back | Complete |
| Source-profile editor | Select firm and reveal/focus URL-targeted canonical artifact | Complete |
| Pull REST identity | Supply stable firm and artifact identity to browser clients | Complete; unchanged |
| Source-profile authority | Own all configuration validation and revision publication | Complete; unchanged |
| Acquisition and persistence | Execute pulls and retain results/evidence | Complete; unchanged |

No modal, popup, alternate editing surface, source-profile write on navigation, or new persistence
authority was introduced. TASK-007 remains the next planned architectural layer.
