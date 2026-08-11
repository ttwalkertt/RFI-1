# Borderline candidates requiring human selection

RFIQA-063 through RFIQA-066 are deliberately excluded from the 62-case objective core by
`adjudicability.status = borderline` and `human_review_required = true`. Their reference records are
candidate hypotheses, not assertions that reasonable reviewers must agree.

## RFIQA-063 — undefined “substantial” reduction

- **Why borderline:** The decrease from 10.2 to 9.2 minutes (about 9.8%) is exact, but no evidence or
  question rule defines “substantial.” Different operational settings can reasonably apply
  different thresholds.
- **Candidate reference:** `indeterminate` with `undefined_evaluation_criterion`.
- **Accept only if:** benchmark owners want to test whether QA treats an undefined evaluative term
  as indeterminate.
- **Alternative revision:** define a threshold such as “substantial means at least 15%.” The same
  submission would then become objectively defective.

## RFIQA-064 — omitted 2% SLA exception set

- **Why borderline:** Twenty of 1,000 requests exceeded the target, but the fixture does not say
  whether the SLA requires 100%, 99%, 95%, or another level. The existence of exceptions is
  objective; the materiality of omitting them is not.
- **Candidate reference:** `defective` with `qualification_omitted`.
- **Reject as objective unless:** an SLA threshold or explicit obligation to report every exception
  is added.
- **Alternative revision:** state “the target is met only if at least 99% complete within target.”
  That would make both the SLA result and the importance of the 2% exception set deterministic.

## RFIQA-065 — direct CEO attribution from double hearsay

- **Why borderline:** The provenance chain is unambiguous, but teams may differ on whether “the CEO
  said” is a material defect when the source only says an analyst heard Dana characterize how the
  CEO seemed.
- **Candidate reference:** `defective` with `provenance_authority_error`.
- **Accept only if:** investigation policy explicitly distinguishes direct executive evidence from
  second-hand impressions and treats upgrading one to the other as material.
- **Alternative revision:** add an answer requirement that direct attribution is permitted only for
  a recording, transcript, signed statement, or verbatim quotation with named provenance.

## RFIQA-066 — undefined “near term” forecast horizon

- **Why borderline:** The 98-day elapsed interval is exact, but “near term” has no fixture-defined
  duration. Domain expectations could reasonably classify the interval differently.
- **Candidate reference:** `indeterminate` with `undefined_evaluation_criterion`.
- **Accept only if:** benchmark owners intentionally want undefined-horizon calibration in the
  candidate set.
- **Alternative revision:** define “near term” as within 60 calendar days. The submitted conclusion
  would then be objectively defective because the first improvement occurred on day 98.

No borderline candidate should enter an objective benchmark merely because its current reference
label looks plausible. Acceptance should either preserve indeterminacy as the tested truth or add
the missing governing criterion and re-review the revised case.
