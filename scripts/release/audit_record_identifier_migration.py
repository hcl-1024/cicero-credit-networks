#!/usr/bin/env python3
"""Audit the complete legacy-to-SEC identifier migration between two commits."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORMER_PREFIX = bytes((86, 82, 66))
CURRENT_PREFIX = b"SEC"
HANDLE_FAMILIES = (b"STAGED", b"WORKER", b"MISSING", b"DELTA", b"SUPP")
FORMER_STAGED_PATTERN = re.compile(re.escape(FORMER_PREFIX) + rb"-STAGED-[0-9]{4}")
CURRENT_STAGED_PATTERN = re.compile(rb"SEC-STAGED-[0-9]{4}")
FORMER_HANDLE_PATTERN = re.compile(
    re.escape(FORMER_PREFIX) + rb"-(?:STAGED|WORKER|MISSING|DELTA|SUPP)-[0-9]+"
)
CURRENT_HANDLE_PATTERN = re.compile(rb"SEC-(?:STAGED|WORKER|MISSING|DELTA|SUPP)-[0-9]+")

PAPER_FACING_FILES = (
    "results/official/headline_values.csv",
    "results/official/o5_6_distribution_grid.csv",
    "results/official/o5_6_distribution_values.csv",
    "results/official/o5_6_k_sensitivity.csv",
    "results/official/o5_6_participation_sensitivity.csv",
    "results/official/o5_missing_edge_probability_rule_sensitivity.csv",
    "results/official/o6_denominator_policy_sensitivity.csv",
    "results/official/o6_density_discount_sensitivity.csv",
    "results/official/paper_findings.csv",
    "docs/paper_findings_manifest.csv",
    "paper/Li_2026_Credit_Under_Pressure_Working_Paper_v1.0.pdf",
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def tracked_files(commit: str, prefix: str | None = None) -> list[str]:
    args = ["ls-tree", "-r", "--name-only", commit]
    if prefix:
        args.extend(["--", prefix])
    return git(*args).decode().splitlines()


def blob(commit: str, path: str) -> bytes:
    return git("show", f"{commit}:{path}")


def identifiers(commit: str, pattern: re.Pattern[bytes]) -> set[str]:
    found: set[str] = set()
    for path in tracked_files(commit):
        found.update(match.decode() for match in pattern.findall(blob(commit, path)))
    return found


def allowed_changed_path(path: str) -> bool:
    return (
        path == "CHANGELOG.md"
        or path == "CITATION.cff"
        or path == "README.md"
        or path.startswith("data/")
        or path == "paper/README.md"
        or path.startswith("results/official/objective_05_06/")
        or path.startswith("results/official/objectives/04_credit_mechanisms/")
        or path == "scripts/analysis/analyze_cicero_loans.py"
        or path == "scripts/objective_05_06/run_recalculation_v5.py"
        or path == "scripts/release/audit_record_identifier_migration.py"
        or path.startswith("docs/audits/")
        or path == "validation/checksums.sha256"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="4dd535b3b20d8b8f61ced205fcc88bd869800272")
    parser.add_argument("--target", default="HEAD")
    args = parser.parse_args()

    failures: list[str] = []
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            failures.append(f"{name}: {detail}")

    git("cat-file", "-e", f"{args.base}^{{commit}}")
    git("cat-file", "-e", f"{args.target}^{{commit}}")

    former_staged_ids = identifiers(args.base, FORMER_STAGED_PATTERN)
    current_staged_ids = identifiers(args.target, CURRENT_STAGED_PATTERN)
    former_handles = identifiers(args.base, FORMER_HANDLE_PATTERN)
    current_handles = identifiers(args.target, CURRENT_HANDLE_PATTERN)
    former_prefix_text = FORMER_PREFIX.decode()
    expected_current_handles = {
        value.replace(f"{former_prefix_text}-", "SEC-", 1) for value in former_handles
    }
    target_former_handles = identifiers(args.target, FORMER_HANDLE_PATTERN)

    check("baseline_staged_identifier_count", len(former_staged_ids) == 95, f"found {len(former_staged_ids)} distinct baseline staged identifiers")
    check("target_staged_identifier_count", len(current_staged_ids) == 95, f"found {len(current_staged_ids)} distinct target staged identifiers")
    check("baseline_all_handle_count", len(former_handles) == 163, f"found {len(former_handles)} distinct baseline handles")
    check("target_all_handle_count", len(current_handles) == 163, f"found {len(current_handles)} distinct target handles")
    check("identifier_bijection", current_handles == expected_current_handles, "target handles exactly equal the prefix-renamed baseline set")
    check("no_former_handles", not target_former_handles, f"found {len(target_former_handles)} former handles in the target tree")

    base_data = tracked_files(args.base, "data")
    target_data = tracked_files(args.target, "data")
    check("data_file_inventory", base_data == target_data, f"base={len(base_data)} files; target={len(target_data)} files")
    data_mismatches = []
    for path in base_data:
        normalized_target = blob(args.target, path)
        for family in HANDLE_FAMILIES:
            normalized_target = normalized_target.replace(
                CURRENT_PREFIX + b"-" + family + b"-",
                FORMER_PREFIX + b"-" + family + b"-",
            )
        if blob(args.base, path) != normalized_target:
            data_mismatches.append(path)
    check("data_content_invariance", not data_mismatches, f"non-label differences: {data_mismatches}")

    canonical_bytes = blob(args.target, "data/canonical/cicero_credit_records.csv")
    canonical_rows = list(csv.DictReader(io.StringIO(canonical_bytes.decode())))
    primary_ids = [row["merged_record_id"] for row in canonical_rows]
    primary_sec = [value for value in primary_ids if value.startswith("SEC-STAGED-")]
    referenced_sec = {match.decode() for match in CURRENT_STAGED_PATTERN.findall(canonical_bytes)}
    check(
        "canonical_structure",
        len(canonical_rows) == 114 and len(primary_ids) == len(set(primary_ids)),
        f"rows={len(canonical_rows)}; unique primary IDs={len(set(primary_ids))}",
    )
    check(
        "canonical_identifier_coverage",
        len(primary_sec) == 68 and len(referenced_sec) == 95,
        f"primary SEC IDs={len(primary_sec)}; all SEC IDs referenced={len(referenced_sec)}",
    )

    numerical_changes = [path for path in PAPER_FACING_FILES if blob(args.base, path) != blob(args.target, path)]
    check("paper_and_value_invariance", not numerical_changes, f"changed protected files: {numerical_changes}")

    changed_files = git("diff", "--name-only", args.base, args.target).decode().splitlines()
    unexpected_paths = [path for path in changed_files if not allowed_changed_path(path)]
    check("change_scope", not unexpected_paths, f"changed={len(changed_files)} files; unexpected={unexpected_paths}")

    result = {
        "status": "PASS" if not failures else "FAIL",
        "base_commit": args.base,
        "target_commit": args.target,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
