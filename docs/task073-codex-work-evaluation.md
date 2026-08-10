# TASK-073 Codex Work experiment evaluation

## Experimental record

The bounded experiment used the unchanged TASK-071 retained Seagate state at repository snapshot
`sqlite-revision-8237`: 21 indexed and eligible documents, 2,268 transcript segments, and
source-effective dates from 2024-09-04 through 2026-07-28. The process-local access generation was
healthy, complete within its declared build bound, and stable under generation ID
`transcript-access-300c2a276641d1b507e104607e71b31bd388699cd0da197c4aba1ed8a9ba5307`.
The retained database and 2,934 content files had identical before/after fingerprints.

Each case ran as an ephemeral, read-only Codex 0.145.0 process with no user configuration, no
repository instructions, no internet evidence, and only the local RFI MCP server. No model override
was supplied. The complete RFI-specific prompt material was one orientation sentence:

> RFI is the retained-evidence source for this task. Answer this research question using only RFI
> retained evidence:

The question followed verbatim. No procedural prompt, search hint, corpus inventory, citation rule,
stopping rule, TASK-071 protocol, or recovery instruction was supplied.

The initial sandboxed launcher attempt failed before MCP initialization because Codex could not
initialize its in-process app-server client under the host sandbox. That negative control is retained
separately. The same experiment command and prompt were then run with the required host permission;
all five cases completed. This startup failure is an experiment-host failure, not an RFI/MCP access
failure.

## Comparative results

| Case | Codex Work + MCP result | TASK-071 baseline | Evaluation |
| --- | --- | --- | --- |
| Sentiment | A useful seven-call recovery-to-scarcity narrative with seven verified segment URI citations and one explicit missing-quarter caution. | Partial/bounded because the answer did not cover the 2024-09-04 corpus boundary; eight mapped exact spans. | Substantively useful, but Codex called the selected title-derived subset “seven retained earnings calls” despite the corpus's missing event-kind metadata and did not acknowledge the 2024-09-04 boundary. Weaker scope calibration than TASK-071. |
| Demand | Detailed period-by-period account of cloud/nearline demand, customer commitments, capacity limits, and price discipline. | Supported/strong with eight claim-to-evidence mappings and stated gaps. | Analytical content is broadly comparable, but the final answer contains no stable segment URI or exact claim-to-evidence map despite 15 verified artifact-byte reads. Exact citation integrity is materially weaker. |
| Technology | Rich chronology of HAMR/Mozaic qualification, production, volume, and bottleneck changes through July 2026. | Supported/strong with eight exact mapped spans and no gaps. | Discovery and synthesis are strong. The report cites date/title/segment ordinal rather than stable RFI segment URIs, so evidence is human-locatable but not unambiguously machine-addressable. Six out-of-schema bound requests were correctly rejected before recovery. |
| 40-TB chronology | Claimed first mention on 2024-12-11 and latest on 2026-03-03, with three verified segment URI citations. | Correctly identified 2024-09-04 and 2026-07-28, with four exact mapped spans. | Material failure. The MCP returned 2024-09-04 first and 2026-07-28 first in the respective ordered result sets, but the runtime selected later candidates and stopped. |
| Attrition negative control | Correctly concluded that retained evidence was insufficient and reported no occurrence of “attrition.” | Correctly `insufficient`, with no accepted claims and an explicit retained-corpus gap. | Correct conclusion after 30 reformulations. The report should also have surfaced missing speaker metadata and indeterminate historical coverage; its absence statement was lexical-index scoped, not proof of real-world absence. |

The experiment did not require identical paths or prose. It did require reliable chronology, exact
evidence mapping, qualification, insufficiency calibration, and unsupported-claim control. On those
criteria, the runtime was strong on substantive discovery in three positive cases and correct on the
negative control, but materially below TASK-071 on temporal-boundary discipline, citation admission,
scope qualification, and calibrated stopping.

No independently reviewable artifact or locator for the ticket's “existing independent analysis”
exists in the repository, TASK-071 retained state, prior review packages, or task documentation.
Accordingly, this checkout supports a reproducible comparison against TASK-071 only. The missing
external comparator is recorded as an evidence limitation; no conclusions are attributed to an
unavailable reference.

## Diagnostic attribution

### Repository/MCP/access failures

None were observed in the five completed cases. All requests used one ready, complete generation and
one repository snapshot. Ordered lexical search exposed the correct chronology boundary candidates,
exact segment and byte reads verified retained artifact identity and digests, bounds and truncation
were visible, empty results remained distinct from failures, and the retained state did not change.

### Retrieval-quality failures

None were established. Lexical retrieval found the relevant boundary, demand, and technology
evidence under reasonable terms. Candidate ranking can remain provisional, but it did not cause the
material chronology failure: the correct oldest/latest dates were already the leading temporally
ordered candidates.

### Investigative-runtime failures

- The chronology investigation ignored the leading 2024-09-04 and 2026-07-28 candidates returned by
  the requested oldest/latest searches, expanded later candidates, and stopped with false bounds.
- The technology investigation submitted four requests with `limit=100` despite the visible maximum
  of 50 and two requests with `max_per_document=50` despite the visible maximum of 10. RFI rejected
  all six as typed invalid requests and Codex recovered without changing the surface.
- Sentiment first passed the server's descriptive identity instead of its client-configured alias to
  Codex's generic resource reader. The client rejected the unknown alias before an MCP request was
  made; Codex then retried with the configured `rfi` alias and completed the exact read. This was a
  non-material runtime discovery/orchestration error, not an RFI evidence absence or access outage.
- The negative control used 30 searches and reached the right conclusion, but did not turn available
  dictionary coverage and speaker-metadata facts into a fully calibrated insufficiency statement.
- Sentiment investigation selected a title-derived call subset without fully reconciling it to the
  declared event-kind limitation or retained temporal boundary.

### Repository-authority failures

No new incorrect artifact identity, checksum, provenance, source-effective date, or association was
observed. The pre-existing authority limitations remained visible: historical `event_kind` and
speaker labels are absent, conference titles can conflict with the broad canonical transcript type,
and historical acquisition completeness is indeterminate. Codex did not consistently carry those
limitations into its answers.

### Synthesis failures

- Chronology asserted false first/latest dates even though exact evidence reads were internally valid.
- Demand omitted stable final evidence locators; technology used informal date/title/ordinal
  references instead of stable locators. This is report construction, not evidence-access failure.
- Sentiment overstated its selected subset as the retained earnings-call universe and implied a
  progressively bullish full-series result without the TASK-071 boundary qualification.
- The insufficiency answer omitted repository coverage and speaker-attribution qualifications.

## Efficiency and explainability

MCP request counts were 22 sentiment, 34 demand, 59 technology, 17 chronology, and 34 insufficiency.
The corresponding lexical search counts were 8, 10, 20, 8, and 30. Exact evidence access varied
materially: sentiment read eight segments, chronology five, technology 36, demand read 15 artifact
ranges, and insufficiency read no exact evidence. These counts are secondary quality indicators, but
they make weak stopping and evidence-admission behavior independently diagnosable.

Complete Codex event streams, final answers, stderr, exact prompts and commands, model/runtime
identity, timings, repository fingerprints, and correlated MCP access traces are preserved in the
TASK-073 review package. MCP traces contain no hidden planner state, hypothesis state, or RFI-owned
sufficiency judgment.

## Architectural disposition

**General runtime is not yet a proficient replacement for TASK-071 investigative behavior.**

The bounded RFI/MCP substrate was sufficient to expose retained truth, exact evidence, correct
temporal candidates, semantics, health, and diagnostics without reproducing the investigative
harness. Codex Work nevertheless produced a materially false chronology boundary and weaker
citation/scope calibration. This is evidence against accepting the replacement today, but not a
rejection of the architectural boundary: the observed material failures belong to runtime
investigation and synthesis, not a named RFI/MCP access or retrieval gap.

The experiment stops here. No convenience tool, procedural MCP prompt, semantic retrieval, TASK-071
control logic, or additional evidence type was added. A future bounded task may repeat the same
surface with a runtime that provides stronger native evidence-admission, chronology, and report
construction behavior. Supplying the missing independent-analysis artifact would also permit the
external comparison that this checkout cannot reproduce.
