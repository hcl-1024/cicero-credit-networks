# SEC-STAGED Identifier Migration Audit Handoff

## Purpose

This handoff supports an independent audit of the identifier migration begun on 15 July 2026. The audit must determine whether every former staged-record and provenance prefix was changed to the `SEC` convention without altering historical evidence, record classifications, calculated values, sensitivity results, or the working paper.

This document is an audit specification, not an independent sign-off.

## Commits under audit

- Baseline: `4dd535b3b20d8b8f61ced205fcc88bd869800272`
- Initial staged-record migration: `647ccbd94b99b90378159e37216375da377366a0`
- Migration commit message: `improved record labeling`

The current `main` branch extends the initial migration to the worker, missing-record, delta, and supplement provenance families. Repository release `v1.1.3` packages these changes as **Labeling adjustments**. This handoff remains the specification for independent verification of that release.

## Claims to test

1. The baseline contains 95 staged-record identifiers and 68 provenance handles using the former prefix, for 163 distinct handles in total.
2. The migration contains exactly the corresponding 163 `SEC` handles, including 95 `SEC-STAGED-XXXX` identifiers.
3. No handle using the former prefix remains anywhere in the current tracked tree.
4. Every mapping is one-to-one and changes only the prefix.
5. The canonical release still contains 114 unique primary records: 68 use the new prefix, while 27 additional renamed identifiers remain as references to records merged into canonical survivors.
6. After reversing the prefix substitution in the migration tree, every tracked file under `data/` is byte-for-byte identical to the baseline.
7. Paper-facing values, sensitivity tables, the quantitative claim registry, its manifest, and the working-paper PDF are byte-for-byte unchanged.
8. Changes outside direct labels are limited to identifier-derived occurrence, amount, relation, and proposal identifiers; deterministic hashes and manifests; analysis-script literals; release checksums; and the changelog.
9. A clean reproduction passes all structural, quantitative, sensitivity, and test checks.

## Independent audit procedure

Use a clean clone with both audited commits available.

### 1. Run the migration comparison

From the repository root:

```sh
python3 scripts/release/audit_record_identifier_migration.py
```

The command must finish with `"status": "PASS"`. It independently reads both Git trees rather than trusting the current working files.

### 2. Reproduce from the migration commit

```sh
git switch --detach main
make reproduce-paper-findings
make verify
make test
```

Expected evidence:

- Official O1-O6 reproduction: `PASS`
- Paper findings: 37 quantitative checks and 6 figures
- Paper claim-map verification: 30 mapped items and 37 registry claims, with no errors
- Canonical records: 114
- Graph variants: 13
- Release values checked: 7
- Sensitivity values checked: 453
- Unit tests: 12 passing

### 3. Confirm the protected public artifacts

The automated comparison must report no changes to:

- `results/official/paper_findings.csv`
- `docs/paper_findings_manifest.csv`
- `results/official/headline_values.csv`
- `results/official/o5_6_distribution_values.csv`
- all seven released sensitivity families represented by the distribution grid and six sensitivity files
- `paper/Li_2026_Credit_Under_Pressure_Working_Paper_v1.0.pdf`

### 4. Inspect the diff categories

Review:

```sh
git diff --stat 4dd535b3b20d8b8f61ced205fcc88bd869800272 main
git diff --name-only 4dd535b3b20d8b8f61ced205fcc88bd869800272 main
```

The changed files must be confined to:

- canonical, amount, and reviewed exposure-authority data
- O4 identifier-bearing tables
- O5-O6 typed, intermediate, calculated, and manifest outputs
- the two analysis scripts containing record-specific rules
- the migration audit files
- release checksums
- the changelog

Any changed prose evidence, source citation, party, date, amount, classification, paper-facing value, sensitivity value, or PDF is an audit failure.

## Acceptance criteria

Approve only if every automated check passes, the reproduction and test suite pass in a clean environment, and manual diff review finds no substantive record or numerical change.

Reject or return for correction if:

- any handle using the former prefix remains in the target tree;
- the old and new identifier sets are not exactly one-to-one;
- any `data/` difference remains after reversing the prefix substitution;
- any protected paper-facing artifact changes;
- reproduction produces a different quantitative value;
- an unexpected file category changed; or
- the audit cannot be reproduced from the two named commits.

## Auditor disposition

Record the following in the audit result:

- Auditor name:
- Audit date:
- Environment and Python version:
- Baseline commit verified:
- Migration commit verified:
- Automated migration comparison: PASS / FAIL
- Full reproduction: PASS / FAIL
- Unit tests: PASS / FAIL
- Manual diff review: PASS / FAIL
- Deviations or observations:
- Final disposition: APPROVED / RETURNED FOR CORRECTION

Approval confirms that release `v1.1.3` changes labeling without changing the paper's numerical findings.
