# Proposition-state and answer-quality schema

Every answer case is labeled on two independent dimensions.

- `proposition_state` is one of `supported`, `contradicted`, `indeterminate`, or `mixed`. It records what the declared retained RFI evidence establishes about the propositions made by the submitted answer.
- `answer_quality` is one of `acceptable` or `defective`. It records whether the submitted answer meets the question, scope, qualification, authority, and evidence-mapping obligations.

`indeterminate` is not a quality failure. An answer that correctly explains that retained evidence is insufficient may be acceptable. An answer that asserts a definite conclusion where retained evidence is insufficient is both `indeterminate` and `defective`.

`mixed` is reserved for materially compound answers whose propositions have different states. It is not a synonym for uncertainty.

Reference records keep labels separate from case payloads. Defective references require `primary_failure` and at least one `acceptable_failure_classes` entry; acceptable references require neither.
