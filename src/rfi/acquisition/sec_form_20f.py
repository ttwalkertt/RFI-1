"""Artifact-specific deterministic retrieval policy for canonical SEC Form 20-F."""

from rfi.acquisition.sec_numbered_form import SecNumberedFormAdapter


class SecForm20FAdapter(SecNumberedFormAdapter):
    """Select one latest visible unamended foreign-issuer annual Form 20-F."""

    adapter_id = "sec-form-20f"
    artifact_ids = ("sec_20f",)
    mechanism = "sec-form-20f"
    eligible_form = "20-F"
    amendment_policy = "exclude"
    artifact_multiplicity = "one_latest_visible_foreign_annual_report"
    no_eligible_code = "no_eligible_form_20f"
    semantic_name = "Form 20-F"
