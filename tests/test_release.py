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


if __name__ == "__main__":
    unittest.main()
