"""Artifact-specific deterministic retrieval policy for canonical SEC Form 10-Q."""

from rfi.acquisition.sec_numbered_form import SecNumberedFormAdapter


class SecForm10QAdapter(SecNumberedFormAdapter):
    """Select one latest visible unamended quarterly Form 10-Q primary document."""

    adapter_id = "sec-form-10q"
    artifact_ids = ("sec_10q",)
    mechanism = "sec-form-10q"
    eligible_form = "10-Q"
    amendment_policy = "exclude"
    artifact_multiplicity = "one_latest_visible_quarterly_report"
    no_eligible_code = "no_eligible_form_10q"
    semantic_name = "Form 10-Q"
