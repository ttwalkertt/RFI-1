"""Artifact-specific deterministic retrieval policy for canonical SEC Form 8-K."""

from rfi.acquisition.sec_numbered_form import SecNumberedFormAdapter


class SecForm8KAdapter(SecNumberedFormAdapter):
    """Select one latest visible unamended Form 8-K from a high-frequency stream."""

    adapter_id = "sec-form-8k"
    artifact_ids = ("sec_8k",)
    mechanism = "sec-form-8k"
    eligible_form = "8-K"
    amendment_policy = "exclude"
    artifact_multiplicity = "one_latest_visible_from_current_report_stream"
    no_eligible_code = "no_eligible_form_8k"
    semantic_name = "Form 8-K"
