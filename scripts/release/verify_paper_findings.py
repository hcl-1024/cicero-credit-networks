#!/usr/bin/env python3
"""Verify the paper-to-output claim map against reproduced artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    registry = {row["claim_id"]: row for row in rows(ROOT / "results" / "official" / "paper_findings.csv")}
    mapping = rows(ROOT / "docs" / "paper_findings_manifest.csv")
    errors = []
    for row in mapping:
        if row["verification_status"] != "repository_verified":
            continue
        artifact = ROOT / row["artifact"]
        if not artifact.exists():
            errors.append(f'{row["map_id"]}: missing {row["artifact"]}')
        if row["claim_id"] and row["claim_id"] not in registry:
            errors.append(f'{row["map_id"]}: missing claim {row["claim_id"]}')
    required = {"canonical_records", "ciceronian_direct_edges", "ciceronian_context_edges", "cicero_removed_edges", "o5_t5_hs", "o56_hs", "o6w_t5a_hs"}
    errors.extend(f"missing required registry claim {claim}" for claim in sorted(required - set(registry)))
    expected = {
        "canonical_records": "114",
        "ciceronian_direct_edges": "89", "ciceronian_direct_records": "80", "ciceronian_direct_largest_component": "53",
        "ciceronian_context_edges": "202", "ciceronian_context_records": "78", "ciceronian_context_largest_component": "98",
        "cicero_removed_edges": "164", "cicero_removed_records": "76", "cicero_removed_largest_component": "72",
        "o5_t4_hs": "6295833.333333", "o5_t5_missing_edge_increment_hs": "35307457.374002",
        "o5_t5_hs": "41603290.707335", "o5_accepted_share_percent": "15.1", "o5_modeled_share_percent": "84.9",
        "o56_hs": "3677083.333333", "o6w_t5a_hs": "1436684112", "o5_imputed_amount_hs": "362500",
        "o5_candidate_count": "199", "o5_expected_edge_mass": "97.39988241104", "o6_effective_population": "17.374713207607",
        "distribution_selected_min_hs": "1009790286", "distribution_selected_max_hs": "3637491303",
        "distribution_grid_rows": "78", "distribution_grid_at_least_1b": "75",
        "participation_grid_rows": "312", "participation_grid_100m_to_999m": "122", "participation_grid_min_hs": "242678645",
        "k_grid_rows": "46", "probability_rule_rows": "5", "denominator_policy_rows": "3", "density_discount_rows": "9",
        "o6_ratio_to_600m": "2.394474", "refinancing_chains": "17", "acute_refinancing_chains": "7",
    }
    for claim, value in expected.items():
        actual = registry.get(claim, {}).get("value")
        if actual != value:
            errors.append(f"{claim}: expected {value}, found {actual}")
    result = {"status": "FAIL" if errors else "PASS", "mapped_items": len(mapping), "registry_claims": len(registry), "errors": errors}
    target = ROOT / "build" / "paper_findings" / "verification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
