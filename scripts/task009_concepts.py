#!/usr/bin/env python3
"""Operate and prove the TASK-009 concept catalog and local admin console."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.concepts import (  # noqa: E402
    CalculationError,
    ConceptDraft,
    ConceptError,
    ConceptRepository,
    ConceptService,
    ConceptStatus,
    MethodKind,
    ObservationMethod,
    ObservationOrigin,
    ObservationService,
    sample_concepts,
)


def emit(value: Any) -> None:
    """Print deterministic JSON for operator and review automation."""
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def seed(repository: ConceptRepository) -> list[str]:
    """Add missing proof concepts through the catalog public create contract."""
    existing = {item.concept_id for item in repository.lookup()}
    created: list[str] = []
    for draft in sample_concepts():
        if draft.concept_id not in existing:
            repository.create(draft)
            created.append(draft.concept_id)
    return created


def extracted_observations(
    repository: ConceptRepository,
) -> dict[str, Any]:
    """Create independent financial proof inputs with exact method and revision identities."""
    observations = ObservationService()
    common = {
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "scope": "example-consolidated",
        "dimensions": {"entity": "example-company"},
        "provenance": ({"source_object_id": "proof-source-object"},),
    }
    revenue = observations.observe(
        repository.get("revenue"),
        "reported-revenue",
        1000,
        unit="USD",
        **common,
    )
    gross_profit = observations.observe(
        repository.get("gross-profit"),
        "reported-gross-profit",
        400,
        unit="USD",
        **common,
    )
    cost = observations.observe(
        repository.get("cost-of-revenue"),
        "reported-cost-of-revenue",
        600,
        unit="USD",
        **common,
    )
    reported = observations.observe(
        repository.get("gross-margin"),
        "reported-gross-margin",
        40.1,
        unit="percent",
        **common,
    )
    calculated_profit = observations.calculate(
        repository.get("gross-margin"),
        "gross-profit-over-revenue",
        {"gross_profit": gross_profit, "revenue": revenue},
    )
    calculated_cost = observations.calculate(
        repository.get("gross-margin"),
        "revenue-less-cost-over-revenue",
        {"revenue": revenue, "cost_of_revenue": cost},
    )
    comparison = observations.reconcile(reported, calculated_profit, 0.2)
    return {
        "inputs": [asdict(revenue), asdict(gross_profit), asdict(cost)],
        "coexisting_gross_margin_observations": [
            asdict(reported),
            asdict(calculated_profit),
            asdict(calculated_cost),
        ],
        "reconciliation": asdict(comparison),
    }


def nonnumeric_observations(repository: ConceptRepository) -> dict[str, Any]:
    """Prove scoped state and multi-shaped event concepts without numeric coercion."""
    service = ObservationService()
    qualification = service.observe(
        repository.get("hamr-qualification"),
        "qualification-state",
        {
            "state": "qualified",
            "customer_scope": "example-customer",
            "product_scope": "example-platform",
            "as_of": "2024-01-24",
        },
        origin=ObservationOrigin.EXTRACTED,
        effective_at="2024-01-24",
        scope="customer:example-customer/product:example-platform",
        provenance=({"source_object_id": "hamr-qualification-proof"},),
    )
    milestone = service.observe(
        repository.get("hamr-shipments"),
        "shipment-milestone",
        {
            "event_type": "volume-shipments-started",
            "product_scope": "example-platform",
        },
        effective_at="2024-06-28",
        scope="product:example-platform",
        provenance=({"source_object_id": "hamr-shipment-proof"},),
    )
    units = service.observe(
        repository.get("hamr-shipments"),
        "units-shipped",
        1000,
        unit="unit",
        period_start="2024-04-01",
        period_end="2024-06-30",
        scope="product:example-platform",
        provenance=({"source_object_id": "hamr-volume-proof"},),
    )
    return {
        "qualification_state": asdict(qualification),
        "shipment_shapes": [asdict(milestone), asdict(units)],
    }


def failure(
    function: Callable[[], Any],
    expected: tuple[type[BaseException], ...] = (ConceptError,),
) -> str:
    """Return an expected visible failure message or fail the proof."""
    try:
        function()
    except expected as error:
        return str(error)
    raise RuntimeError("expected failure did not occur")


def request_json(url: str) -> tuple[int, dict[str, Any]]:
    """Read a JSON endpoint through the actual local HTTP server."""
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        result = error.code, json.loads(error.read())
        error.close()
        return result


def serve_once(state: Path) -> dict[str, Any]:
    """Start on an ephemeral local port, exercise API/GUI routes, and shut down cleanly."""
    server = create_admin_server(state, port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        health = request_json(f"http://{host}:{port}/health")
        concepts = request_json(f"http://{host}:{port}/api/concepts?q=HAMR")
        invalid = request_json(f"http://{host}:{port}/api/not-a-route")
        traversal = request_json(f"http://{host}:{port}/api/../catalog.json")
        with urllib.request.urlopen(f"http://{host}:{port}/concepts", timeout=3) as response:
            html = response.read().decode()
        return {
            "address": f"http://{host}:{port}",
            "health": health,
            "lookup_count": len(concepts[1]["items"]),
            "invalid_request": invalid,
            "traversal_request": traversal,
            "console_shell": "RFI Admin Console" in html and "Concept Catalog" in html,
            "clean_shutdown": True,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def proof(root: Path) -> dict[str, Any]:
    """Run lifecycle, persistence, derivation, failure, API, and security proofs."""
    state = root / "catalog"
    repository = ConceptRepository.initialize(state)
    seeded = seed(repository)
    lookups = {
        "id": [item.concept_id for item in repository.lookup("gross-margin")],
        "name": [item.concept_id for item in repository.lookup("Gross Margin")],
        "alias": [item.concept_id for item in repository.lookup("GM")],
        "keyword": [item.concept_id for item in repository.lookup("qualification")],
        "tag": [item.concept_id for item in repository.lookup(tag="multi-shaped")],
        "status": [
            item.concept_id for item in repository.lookup(status=ConceptStatus.ACTIVE)
        ],
        "validity": [
            item.concept_id for item in repository.lookup(valid_on="2024-06-28")
        ],
    }
    generic = ConceptDraft(
        concept_id="generic-operational-signal",
        display_name="Generic Operational Signal",
        definition="A proof concept whose future domain semantics are intentionally open.",
        comments="Created through the public programmatic contract.",
        aliases=("generic signal",),
        hints=("operator supplied signal",),
        status=ConceptStatus.DRAFT,
        tags=("generic", "proof"),
        classifications={"proof_family": "generic"},
        valid_from="2024-01-01",
        sample_date="2024-02-01",
        methods=(
            ObservationMethod(
                method_id="generic-extracted",
                kind=MethodKind.EXTRACTED,
                name="Generic extracted quantity",
                result_shape="quantity",
                units=("unit",),
            ),
            ObservationMethod(
                method_id="generic-derived",
                kind=MethodKind.DETERMINISTIC,
                name="Generic deterministic passthrough ratio",
                result_shape="ratio",
                required_inputs=("revenue",),
                configuration={
                    "operation": "add",
                    "output_unit": "ratio",
                    "inputs": [
                        {"role": "revenue", "concept_id": "revenue", "unit": "USD"}
                    ],
                },
            ),
        ),
    )
    first = repository.create(generic)
    revised_draft = replace(
        generic,
        comments=generic.comments + " Metadata and comments edited.",
        aliases=generic.aliases + ("operational proof signal",),
        valid_through="2026-12-31",
        sample_date="2024-03-01",
        status=ConceptStatus.ACTIVE,
    )
    second = repository.revise(generic.concept_id, revised_draft, first.revision_id)
    retired = repository.retire(generic.concept_id, second.revision_id)
    history = repository.history(generic.concept_id)
    restarted = ConceptRepository.open(state)
    restart_integrity = restarted.verify()
    financial = extracted_observations(restarted)
    nonnumeric = nonnumeric_observations(restarted)

    invalid_method = ObservationMethod(
        method_id="unknown",
        kind="not-registered",
        name="Unknown",
        result_shape="structured",
    )
    bad_derivation = ObservationMethod(
        method_id="bad-derivation",
        kind=MethodKind.DETERMINISTIC,
        name="Bad derivation",
        result_shape="ratio",
        required_inputs=("input",),
        configuration={"operation": "execute-python", "inputs": []},
    )
    failures = {
        "invalid_identifier": failure(
            lambda: repository.create(replace(generic, concept_id="../unsafe"))
        ),
        "duplicate_identifier": failure(lambda: repository.create(generic)),
        "invalid_validity": failure(
            lambda: repository.create(
                replace(generic, concept_id="bad-validity", valid_through="2023-01-01")
            )
        ),
        "malformed_method_configuration": failure(
            lambda: repository.create(
                replace(
                    generic,
                    concept_id="bad-config",
                    methods=(replace(generic.methods[0], configuration=[]),),
                )
            )
        ),
        "unknown_method_kind": failure(
            lambda: repository.create(
                replace(generic, concept_id="bad-kind", methods=(invalid_method,))
            )
        ),
        "invalid_deterministic_derivation": failure(
            lambda: repository.create(
                replace(generic, concept_id="bad-derivation", methods=(bad_derivation,))
            )
        ),
        "invalid_revision_update": failure(
            lambda: repository.revise(generic.concept_id, revised_draft, first.revision_id)
        ),
        "missing_inputs": failure(
            lambda: ObservationService().calculate(
                repository.get("gross-margin"), "gross-profit-over-revenue", {}
            ),
            (CalculationError,),
        ),
    }
    revenue_observation = ObservationService().observe(
        repository.get("revenue"),
        "reported-revenue",
        1000,
        unit="USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
        scope="scope-a",
    )
    bad_unit = replace(revenue_observation, unit="EUR")
    gross_profit_observation = ObservationService().observe(
        repository.get("gross-profit"),
        "reported-gross-profit",
        400,
        unit="USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
        scope="scope-a",
    )
    failures["incompatible_units"] = failure(
        lambda: ObservationService().calculate(
            repository.get("gross-margin"),
            "gross-profit-over-revenue",
            {"gross_profit": gross_profit_observation, "revenue": bad_unit},
        ),
        (CalculationError,),
    )
    wrong_period = replace(revenue_observation, period_start="2023-01-01")
    failures["incompatible_periods"] = failure(
        lambda: ObservationService().calculate(
            repository.get("gross-margin"),
            "gross-profit-over-revenue",
            {"gross_profit": gross_profit_observation, "revenue": wrong_period},
        ),
        (CalculationError,),
    )
    zero_revenue = replace(revenue_observation, value=0)
    failures["calculation_failure"] = failure(
        lambda: ObservationService().calculate(
            repository.get("gross-margin"),
            "gross-profit-over-revenue",
            {"gross_profit": gross_profit_observation, "revenue": zero_revenue},
        ),
        (CalculationError,),
    )
    interrupted = replace(generic, concept_id="interrupted-proof")
    failures["interrupted_write"] = failure(
        lambda: repository.create(interrupted, fail_before_publish=True)
    )
    historical = first
    mutated = replace(historical, comments="silent rewrite")
    failures["attempted_historical_mutation"] = failure(
        lambda: repository._write_revision(mutated)
    )
    corrupt_state = root / "corrupt-catalog"
    shutil.copytree(state, corrupt_state)
    pointer = corrupt_state / "catalog.json"
    pointer.write_text("{broken", encoding="utf-8")
    failures["corrupted_catalog_state"] = failure(
        lambda: ConceptRepository.open(corrupt_state)
    )
    server_first = serve_once(state)
    server_restart = serve_once(state)
    checks = {
        "seeded_proof_set": set(seeded)
        >= {"revenue", "gross-margin", "hamr-qualification", "hamr-shipments"},
        "lookup_all_modes": all(lookups.values()),
        "revision_history_preserved": [item.revision_number for item in history] == [1, 2, 3],
        "retirement_is_revision": retired.status == ConceptStatus.RETIRED,
        "restart_persistence": restart_integrity["result"] == "PASS",
        "extracted_and_calculated_coexist": len(
            financial["coexisting_gross_margin_observations"]
        ) == 3,
        "lineage_preserved": all(
            item["lineage"]
            for item in financial["coexisting_gross_margin_observations"]
            if item["origin"] == "calculated"
        ),
        "stateful_nonnumeric": nonnumeric["qualification_state"]["result_shape"] == "state",
        "event_and_quantity_shapes": len(nonnumeric["shipment_shapes"]) == 2,
        "failures_visible": len(failures) >= 13,
        "local_server_and_console": server_first["console_shell"],
        "server_restart": server_restart["health"][0] == 200,
        "invalid_browser_request": server_first["invalid_request"][0] == 404,
        "unsafe_path_rejected": server_first["traversal_request"][0] == 400,
        "programmatic_interface": ConceptService(restarted).detail("revenue").concept_id
        == "revenue",
    }
    if not all(checks.values()):
        raise RuntimeError(f"TASK-009 proof failed: {checks}")
    return {
        "state": str(state),
        "catalog_integrity": restart_integrity,
        "seeded": seeded,
        "lookups": lookups,
        "generic_lifecycle": {
            "created": asdict(first),
            "revised": asdict(second),
            "retired": asdict(retired),
            "history": [asdict(item) for item in history],
        },
        "financial_proof": financial,
        "nonnumeric_proof": nonnumeric,
        "failure_proofs": failures,
        "server_proof": {"first": server_first, "restart": server_restart},
        "checks": checks,
    }


def parser() -> argparse.ArgumentParser:
    """Build the programmatic operator interface."""
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    for name in ("init", "list", "show", "history", "verify", "serve", "fixture-proof"):
        command = commands.add_parser(name)
        command.add_argument(
            "--state",
            type=Path,
            default=ROOT / ".artifacts/runtime/TASK-009/catalog",
        )
        if name == "init":
            command.add_argument("--seed", action="store_true")
        if name == "list":
            command.add_argument("--query", default="")
            command.add_argument("--tag")
            command.add_argument("--status")
            command.add_argument("--valid-on")
        if name in {"show", "history"}:
            command.add_argument("--id", required=True)
        if name == "serve":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8765)
    return value


def main() -> int:
    """Execute catalog lifecycle, lookup, proof, or local-console commands."""
    arguments = parser().parse_args()
    if arguments.command == "fixture-proof":
        if arguments.state == ROOT / ".artifacts/runtime/TASK-009/catalog":
            with tempfile.TemporaryDirectory() as temporary:
                emit(proof(Path(temporary)))
        else:
            arguments.state.parent.mkdir(parents=True, exist_ok=True)
            emit(proof(arguments.state.parent))
        return 0
    repository = ConceptRepository.initialize(arguments.state)
    if arguments.command == "init":
        created = seed(repository) if arguments.seed else []
        emit({"state": str(arguments.state), "seeded": created, **repository.verify()})
    elif arguments.command == "list":
        service = ConceptService(repository)
        items = service.list_concepts(
            arguments.query,
            arguments.tag,
            arguments.status,
            arguments.valid_on,
        )
        emit({"items": [asdict(item) for item in items]})
    elif arguments.command == "show":
        emit(asdict(repository.get(arguments.id)))
    elif arguments.command == "history":
        emit({"items": [asdict(item) for item in repository.history(arguments.id)]})
    elif arguments.command == "verify":
        emit(repository.verify())
    elif arguments.command == "serve":
        server = create_admin_server(arguments.state, arguments.host, arguments.port)
        host, port = server.server_address
        print(f"RFI Admin Console: http://{host}:{port}", flush=True)
        print("Press Ctrl-C for clean shutdown.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
