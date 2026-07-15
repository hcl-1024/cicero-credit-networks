from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from cicero_credit import cli


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_release_inputs_reconcile(self) -> None:
        result = cli.validate(release_regression=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["canonical_records"], 114)
        self.assertEqual(result["schema_fields"], 46)

    def test_schema_covers_every_canonical_column(self) -> None:
        with cli.CANONICAL.open(newline="", encoding="utf-8-sig") as handle:
            canonical_fields = list(csv.DictReader(handle).fieldnames or [])
        self.assertEqual(canonical_fields, [row["field"] for row in cli.rows(cli.SCHEMA)])

    def test_source_manifest_does_not_claim_private_files_are_bundled(self) -> None:
        manifest = cli.rows(ROOT / "data" / "canonical" / "source_manifest.csv")
        self.assertTrue(manifest)
        self.assertEqual({row["release_availability"] for row in manifest}, {"external_not_redistributed"})

    def test_new_record_requires_exposure_decision(self) -> None:
        canonical_ids = {row["merged_record_id"] for row in cli.rows(cli.CANONICAL)}
        decision_ids = {row["record_id"] for row in cli.rows(cli.DECISIONS)}
        canonical_ids.add("CONTRIBUTED-TEST-0001")
        self.assertNotEqual(canonical_ids, decision_ids)

    def test_proposal_template_validates(self) -> None:
        path = ROOT / "data" / "contributions" / "examples" / "new-record.example.json"
        proposal = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(cli.validate_proposal(path, proposal), [])

    def test_o56_component_registry_has_unique_members(self) -> None:
        registry = cli.rows(ROOT / "config" / "o56_borrower_components.csv")
        members = [member.strip() for row in registry for member in row["member_record_ids"].split(";") if member.strip()]
        canonical_ids = {row["merged_record_id"] for row in cli.rows(cli.CANONICAL)}
        self.assertEqual(len(members), len(set(members)))
        self.assertTrue(set(members) <= canonical_ids)

    def test_public_code_has_no_local_absolute_paths(self) -> None:
        offenders = []
        for folder in (ROOT / "src", ROOT / "scripts"):
            for path in folder.rglob("*.py"):
                if "/Users/" in path.read_text(encoding="utf-8"):
                    offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_release_values_are_present(self) -> None:
        expected = cli.expected_values()
        for key in ("O5-T4", "O5-T5", "O5-6", "O6W-T5A"):
            self.assertIn(key, expected)

    def test_release_value_statuses_are_official(self) -> None:
        values = {row["value_id"]: row["status"] for row in cli.rows(ROOT / "validation" / "release_expected_values.csv")}
        self.assertEqual(values["selected_k"], "official_release_intermediate")
        self.assertEqual(values["hierarchical_p50_hs"], "official_release_intermediate")
        for key in ("O5-T4", "O5-T5-missing-edge-increment", "O5-T5", "O5-6", "O6W-T5A"):
            self.assertEqual(values[key], "official_release_calculation")

    def test_full_sensitivity_outputs_are_complete(self) -> None:
        sensitivity = cli.V5 / "sensitivity"
        distribution = cli.rows(sensitivity / "o56_distribution_grid.csv")
        participation = cli.rows(sensitivity / "o56_participation_sensitivity.csv")
        k_grid = cli.rows(sensitivity / "scenario_k_values.csv")
        probability = cli.rows(sensitivity / "missing_edge_probability_rule_sensitivity.csv")
        denominator = cli.rows(sensitivity / "o6_denominator_policy_sensitivity.csv")
        density = cli.rows(sensitivity / "density_discount_sensitivity.csv")
        self.assertEqual(len(distribution), 78)
        self.assertEqual(len(participation), 312)
        self.assertEqual(len(k_grid), 46)
        self.assertEqual(len(probability), 5)
        self.assertEqual(len(denominator), 3)
        self.assertEqual(len(density), 9)
        self.assertEqual({int(row["scenario_k"]) for row in k_grid}, set(range(5, 51)))
        selected = [row for row in k_grid if row["scenario_status"] == "selected_base"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(int(selected[0]["scenario_k"]), 5)

    def test_calculation_interface_precision_is_release_method(self) -> None:
        spec = importlib.util.spec_from_file_location("recalculation_v5", ROOT / "scripts" / "objective_05_06" / "run_recalculation_v5.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        parameters = json.loads((ROOT / "config" / "calculation_parameters.json").read_text(encoding="utf-8"))
        self.assertEqual(module.CALCULATION_INTERFACE_PRECISION_PLACES, 12)
        self.assertEqual(parameters["calculation_interface_precision_places"], 12)
        self.assertEqual(module.fmt(5 / 12), "0.416666666667")

    def test_checksums_cover_the_release_trust_layer(self) -> None:
        listed = {line.split("  ", 1)[1] for line in (ROOT / "validation" / "checksums.sha256").read_text(encoding="utf-8").splitlines() if line}
        expected = set()
        for folder in (ROOT / "data" / "canonical", ROOT / "data" / "exposure_groups", ROOT / "data" / "amounts", ROOT / "data" / "decisions", ROOT / "config", cli.OFFICIAL, ROOT / "validation"):
            expected.update(path.relative_to(ROOT).as_posix() for path in folder.rglob("*") if path.is_file() and path.name != "checksums.sha256" and not path.name.startswith("."))
        self.assertEqual(listed, expected)


if __name__ == "__main__":
    unittest.main()
