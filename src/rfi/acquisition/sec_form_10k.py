"""Artifact-specific deterministic retrieval policy for canonical SEC Form 10-K."""

from rfi.acquisition.sec_numbered_form import SecNumberedFormAdapter


class SecForm10KAdapter(SecNumberedFormAdapter):
    """Select one latest visible unamended Form 10-K primary document."""

    adapter_id = "sec-form-10k"
    artifact_ids = ("sec_10k",)
    mechanism = "sec-form-10k"
    eligible_form = "10-K"
    amendment_policy = "exclude"
    artifact_multiplicity = "exactly_one_latest_visible"
    no_eligible_code = "no_eligible_form_10k"
    semantic_name = "Form 10-K"
