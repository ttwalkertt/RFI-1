"""Artifact-specific deterministic retrieval policy for canonical SEC Form 6-K."""

from rfi.acquisition.sec_numbered_form import SecNumberedFormAdapter


class SecForm6KAdapter(SecNumberedFormAdapter):
    """Select one latest visible unamended Form 6-K from an irregular report stream."""

    adapter_id = "sec-form-6k"
    artifact_ids = ("sec_6k",)
    mechanism = "sec-form-6k"
    eligible_form = "6-K"
    amendment_policy = "exclude"
    artifact_multiplicity = "one_latest_visible_from_irregular_current_report_stream"
    no_eligible_code = "no_eligible_form_6k"
    semantic_name = "Form 6-K"
