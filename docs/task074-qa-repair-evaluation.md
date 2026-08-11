# TASK-074 independent QA and bounded-repair evaluation

## Disposition

**QA is useful but additional runtime-side quality controls require a future experiment.**

One independent QA pass found eight supported defects with no unsupported QA #1 findings, and the
bounded repair resolved or improved several of them. It did not materially close the TASK-073
quality gap. QA missed three of eight known targets, QA #2 returned three falsely reassuring
terminal passes, the sentiment repair left evidence-mapping defects, and that repair introduced a
new significant citation regression.

The result remains a valid negative experimental result. Nothing observed justifies changing the
RFI/MCP surface. A next bounded experiment should address first-pass investigator prompting rather
than add another repair cycle, escalation path, reviewer negotiation, or QA-specific MCP behavior.

## Method and independence

The five preserved TASK-073 answers were the fixed proving set. Their expected SHA-256 identities
are embedded in the runner and the complete TASK-073 source directory was fingerprinted before and
after the experiment. No first-pass investigation was rerun.

Each of the 15 stages used a fresh ephemeral Codex context:

`fixed TASK-073 answer -> independent QA #1 -> one bounded repair -> fresh QA #2 -> stop`

Every QA #1 reviewer received only the original question, submitted answer, general retained-corpus
limitations, the QA role/contract, and independent access to the unchanged read-only TASK-073 MCP.
Every repairer received only the question, original answer, structured QA #1 findings, their stable
references, the repair contract, and the same MCP. QA #2 received the question, repaired answer,
QA #1 findings, repair actions, and explicit unresolved items. No stage received TASK-071 answers,
external reference answers, case-specific defect hints, the TASK-073 trace, hidden investigator or
reviewer context, a prescribed search sequence, or an escalation route.

The exact prompts, JSON schemas, structured outputs, complete Codex event streams, correlated MCP
traces, stderr, commands, thread IDs, timings, digests, source fingerprints, and lifecycle records
are preserved. The runtime was `codex-cli 0.145.0`, with user configuration disabled, ephemeral
read-only execution, and no model override. The recorded model selector is therefore exactly
`Codex CLI default`; this CLI event format did not emit the resolved backend model name, so no more
specific identity is inferred.

The retained state remained byte-identical: the SQLite digest was
`925776b832365acd9445288c294f5011bf4c70f93a1623a8855575c759a92907`, and the
2,934-file content manifest digest was
`da57be3d399cf95bc1aa8b2f58c456e84c2b8810645e03fc814ecefe2b190def` before and after.

## Results

| Case | QA #1 findings | QA #1 / repair / QA #2 MCP operations | QA #2 | Diagnostic result |
|---|---:|---:|---|---|
| Sentiment | 3: 2 significant, 1 minor | 12 / 3 / 15 | `repair_required` | Scope and metadata qualification improved; mapping defects remained and repair introduced an incorrect inventory citation |
| Demand | 1 significant | 18 / 12 / 14 | `pass` | Stable mappings added; the terminal pass was diagnostically sound |
| Technology | 1 significant | 21 / 3 / 17 | `pass` | Ambiguous qualification wording improved, but the known stable-locator defect was missed |
| Chronology | 1 material, 1 significant | 17 / 8 / 16 | `pass` | Earliest corrected to 2024-09-04; latest remained falsely fixed at 2026-03-03 rather than 2026-07-28 |
| Insufficiency control | 1 significant | 11 / 3 / 6 | `pass` | Lexical/coverage calibration improved and one limitation was preserved; absent speaker metadata was still omitted |

Total elapsed runtime was 1,141.331 seconds. The stages performed 79 QA #1, 29 repair, and 68 QA #2
MCP operations, 176 operations in total. Three operations returned bounded errors. There were five
and only five repair invocations, no second repair, and no escalation.

### QA #1 detection and false-positive control

Post-run adjudication found all eight QA #1 findings substantively supported and found no
unsupported QA #1 defect demand. Five of eight known TASK-073 targets were detected:

- sentiment scope/event-metadata qualification;
- demand evidence mapping;
- the earliest chronology boundary;
- insufficiency lexical-absence calibration; and
- insufficiency retained-coverage qualification.

Three known targets were missed:

- most of the technology answer still lacked stable RFI locators;
- the chronology answer's latest boundary ignored accessible 2026-07-28 Mozaic 4+ evidence; and
- the insufficiency answer did not disclose that historical speaker labels are absent, preventing
  reliable named-speaker attribution.

The insufficiency reviewer also invented
`rfi://repository-snapshots/sqlite-revision-8237`, which is not a resource on the frozen MCP
surface. Its underlying absence-overstatement finding was still supported by the successful search
trace and corpus resource. This is recorded as reference-integrity failure rather than incorrectly
counted as a false substantive finding.

### Repair effectiveness and terminal review

QA #2 marked seven QA #1 findings resolved and the sentiment mapping finding partially resolved.
That finding's two residual mapping defects are investigator-repair failures because adequate
exact evidence access remained available. Sentiment QA #2 also found a repair-induced significant
regression: a single conference artifact was displayed as the citation for corpus-wide inventory
facts. It additionally double-counted the residual mapping defect as both the partial resolution of
the original finding and a new finding; the defect is real, but the “new” classification is not.

The insufficiency repair explicitly preserved one unresolved item: lexical non-observation cannot
establish semantic absence or complete historical acquisition. QA #2 correctly treated that item
as a repository-authority limitation, not as a reason to escalate. The repair still completed its
other feasible changes and handed the result onward.

Four QA #2 reviews returned `pass`; only demand's pass was diagnostically sound. Technology,
chronology, and insufficiency were false terminal passes because each retained a known
demonstrable defect. QA #2 remained terminal in all cases, as required.

## Diagnostic attribution

- **QA/reviewer failure:** the three missed known targets; the invented insufficiency URI; and the
  three false terminal passes.
- **Investigator repair failure:** residual sentiment claim-to-segment mismatches despite adequate
  MCP access.
- **Repair-induced regression:** the sentiment inventory citation.
- **Repository-authority limitation:** indeterminate semantic absence and historical acquisition
  completeness in the insufficiency control.
- **MCP/access failure:** none established. Accessible evidence exposed the correct chronology and
  stable-locator facts.
- **Unresolved bounded repair:** one explicit insufficiency item, preserved without escalation.

## Architectural evaluation

The experiment preserved the intended ownership boundary. RFI remained the read-only epistemic
substrate; QA findings, repair decisions, and review dispositions remained runtime work products and
did not become repository truth. The orchestration contains only architecture-neutral immutable
contracts, serialization validation, durable case association, and a hard one-cycle state machine.
It does not reuse TASK-071's investigative protocol, closed-record evidence admission, adjudicator,
recovery work orders, tool budgets, final-turn rules, or report generator.

The unchanged MCP was sufficient to reveal all known defects, so this experiment supplies no basis
for QA-specific tools, semantic/vector retrieval, additional evidence types, or MCP mutation. The
main limitations were reviewer selection/stopping and repair synthesis. Because the single loop
improved some answers but failed to reliably detect or confirm remaining errors, the next
experiment should isolate first-pass investigator prompting. TASK-074 intentionally does not design
additional repair or escalation machinery.
