from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "canonical" / "cicero_credit_records.csv"
DECISIONS = ROOT / "data" / "exposure_groups" / "reviewed_record_decisions.csv"
PROPOSALS = ROOT / "data" / "contributions" / "proposals"
OFFICIAL = ROOT / "results" / "official"
V5 = OFFICIAL / "objective_05_06" / "recalculation_v5"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for value in values:
            writer.writerow({key: value.get(key, "") for key in fieldnames})


def proposals() -> list[tuple[Path, dict[str, object]]]:
    found = []
    for path in sorted(PROPOSALS.glob("*.json")):
        found.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return found


def validate_proposal(path: Path, proposal: dict[str, object]) -> list[str]:
    errors: list[str] = []
    required_common = {"proposal_id", "proposal_type", "source_url_or_edition", "contributor_note"}
    missing = sorted(key for key in required_common if not str(proposal.get(key, "")).strip())
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(missing)}")
    try:
        uuid.UUID(str(proposal.get("proposal_id", "")))
    except ValueError:
        errors.append(f"{path}: proposal_id must be a UUID")
    proposal_type = proposal.get("proposal_type")
    allowed = {"new_record", "record_correction", "additional_source", "actor_identity_correction", "exposure_group_suggestion", "amount_normalization_correction"}
    if proposal_type not in allowed:
        errors.append(f"{path}: unsupported proposal_type {proposal_type!r}")
    if proposal_type == "new_record":
        required = {"ancient_source_citation", "date", "latin_evidence", "english_interpretation", "confidence_proposed"}
        missing = sorted(key for key in required if not str(proposal.get(key, "")).strip())
        if missing:
            errors.append(f"{path}: new record is missing: {', '.join(missing)}")
    else:
        targets = proposal.get("relationship_to_existing_records") or proposal.get("target_record_ids")
        if not targets:
            errors.append(f"{path}: this proposal type must identify existing record IDs")
    return errors


def validate(release_regression: bool = False) -> dict[str, object]:
    errors: list[str] = []
    canonical = rows(CANONICAL)
    ids = [row["merged_record_id"] for row in canonical]
    if any(not value for value in ids):
        errors.append("canonical dataset contains a blank merged_record_id")
    if len(ids) != len(set(ids)):
        errors.append("canonical dataset contains duplicate merged_record_id values")
    decision_rows = rows(DECISIONS)
    decision_ids = [row["record_id"] for row in decision_rows]
    if set(ids) != set(decision_ids) or len(decision_ids) != len(set(decision_ids)):
        errors.append("canonical records and reviewed exposure decisions do not reconcile one-to-one")
    if release_regression and len(ids) != 114:
        errors.append(f"release 1.0 regression expects 114 canonical records, found {len(ids)}")
    seen_proposals: set[str] = set()
    for path, proposal in proposals():
        errors.extend(validate_proposal(path, proposal))
        proposal_id = str(proposal.get("proposal_id", ""))
        if proposal_id in seen_proposals:
            errors.append(f"duplicate proposal_id: {proposal_id}")
        seen_proposals.add(proposal_id)
    result = {
        "status": "PASS" if not errors else "FAIL",
        "canonical_records": len(canonical),
        "reviewed_exposure_decisions": len(decision_rows),
        "contribution_proposals": len(seen_proposals),
        "errors": errors,
    }
    if errors:
        raise SystemExit(json.dumps(result, indent=2))
    return result


def run_script(relative: str) -> None:
    subprocess.run([sys.executable, str(ROOT / relative)], cwd=ROOT, check=True)


def clean_generated() -> None:
    for path in (ROOT / "build" / "analysis", OFFICIAL / "objectives", OFFICIAL / "objective_05_06"):
        if path.exists():
            shutil.rmtree(path)


def export_headlines() -> None:
    values = {row["value_id"]: row for row in rows(V5 / "calculated" / "recalculated_values_summary.csv")}
    distributions = rows(V5 / "calculated" / "o56_distribution_values.csv")
    labels = {
        "O5-T4": "Reviewed register baseline",
        "O5-T5-missing-edge-increment": "Controlled missing-edge increment",
        "O5-T5": "Graph-respecting Cicero-community stock",
        "O5-6": "Cicero borrower-side calibration",
        "O6W-T5A": "Weighted 600-senator comparison",
    }
    output = []
    for value_id in labels:
        row = values[value_id]
        output.append({"value_id": value_id, "public_label": labels[value_id], "value": row["value"], "unit": row["unit"], "calculation_window": "45-44 BCE", "method_release": "recalculation_v5"})
    write_csv(OFFICIAL / "headline_values.csv", list(output[0]), output)
    write_csv(OFFICIAL / "o5_6_distribution_values.csv", list(distributions[0]), distributions)


def reproduce() -> None:
    validate()
    clean_generated()
    for script in (
        "scripts/analysis/analyze_cicero_loans.py",
        "scripts/analysis/analyze_loan_edges.py",
        "scripts/analysis/build_actor_graph.py",
        "scripts/analysis/build_objective_01_02_graph_findings.py",
        "scripts/analysis/build_objective_03_intermediaries.py",
        "scripts/analysis/build_objective_04_credit_mechanisms.py",
        "scripts/objective_05_06/run_recalculation_v5.py",
    ):
        run_script(script)
    export_headlines()
    verify()


def expected_values() -> dict[str, float]:
    return {row["value_id"]: float(row["value"]) for row in rows(ROOT / "validation" / "release_expected_values.csv")}


def verify() -> dict[str, object]:
    validation = validate(release_regression=True)
    actual = {row["value_id"]: float(row["value"]) for row in rows(V5 / "calculated" / "recalculated_values_summary.csv")}
    expected = expected_values()
    mismatches = {}
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value is None or abs(actual_value - expected_value) > max(1e-6, abs(expected_value) * 1e-10):
            mismatches[key] = {"expected": expected_value, "actual": actual_value}
    graph_manifest = rows(ROOT / "build" / "analysis" / "graphs" / "tables" / "graph_variant_manifest.csv")
    graph_by_name = {row["variant_name"]: row for row in graph_manifest}
    required_graphs = {"combined_transaction_graph", "ciceronian_period_graph", "cicero_removed_graph"}
    missing_graphs = sorted(required_graphs - set(graph_by_name))
    if mismatches or missing_graphs:
        raise SystemExit(json.dumps({"status": "FAIL", "value_mismatches": mismatches, "missing_graphs": missing_graphs}, indent=2))
    result = {
        "status": "PASS",
        "canonical_records": validation["canonical_records"],
        "release_values_checked": len(expected),
        "graph_variants": len(graph_manifest),
    }
    (ROOT / "validation" / "latest_verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def preview() -> dict[str, object]:
    validate()
    canonical_ids = {row["merged_record_id"] for row in rows(CANONICAL)}
    report_rows = []
    for path, proposal in proposals():
        proposal_type = str(proposal["proposal_type"])
        targets = proposal.get("relationship_to_existing_records") or proposal.get("target_record_ids") or []
        unknown = sorted(str(target) for target in targets if str(target) not in canonical_ids)
        if proposal_type == "new_record":
            affected = "O1;O2;O3;O4 potentially; O5;O5-6;O6 blocked pending exposure review"
        elif proposal_type in {"exposure_group_suggestion", "amount_normalization_correction"}:
            affected = "O5;O5-6;O6 potentially; maintainer review required"
        else:
            affected = "O1-O6 depend on accepted fields; maintainer review required"
        report_rows.append({
            "proposal_id": proposal["proposal_id"],
            "proposal_type": proposal_type,
            "source_file": path.relative_to(ROOT).as_posix(),
            "unknown_target_record_ids": ";".join(unknown),
            "potential_objective_effect": affected,
            "official_results_modified": "no",
            "status": "VALID_PROPOSAL" if not unknown else "NEEDS_TARGET_CORRECTION",
        })
    fields = ["proposal_id", "proposal_type", "source_file", "unknown_target_record_ids", "potential_objective_effect", "official_results_modified", "status"]
    write_csv(ROOT / "build" / "preview" / "proposal_impact.csv", fields, report_rows)
    result = {"status": "PASS", "proposal_count": len(report_rows), "official_results_modified": False}
    (ROOT / "build" / "preview" / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def checksums() -> None:
    selected = [
        CANONICAL,
        ROOT / "data" / "canonical" / "schema.csv",
        ROOT / "data" / "exposure_groups" / "reviewed_record_decisions.csv",
        ROOT / "config" / "calculation_parameters.json",
        ROOT / "config" / "o56_borrower_components.csv",
        OFFICIAL / "headline_values.csv",
        OFFICIAL / "o5_6_distribution_values.csv",
    ]
    lines = []
    for path in selected:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    (ROOT / "validation" / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "reproduce", "verify", "preview", "checksums", "clean"))
    args = parser.parse_args()
    if args.command == "validate":
        result = validate()
    elif args.command == "reproduce":
        reproduce(); checksums(); result = {"status": "PASS", "message": "Official O1-O6 results reproduced"}
    elif args.command == "verify":
        result = verify()
    elif args.command == "preview":
        result = preview()
    elif args.command == "checksums":
        checksums(); result = {"status": "PASS"}
    else:
        clean_generated(); result = {"status": "PASS"}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
