# Cicero Credit Networks

This repository publishes the reviewed record snapshot, exposure-group authorities, and reproducible calculations used to study credit, debt, mediation, and financial pressure in Cicero's correspondence and closely related evidence.

The release contains 114 canonical records. Latin is the control text. Translations, OCR, and secondary scholarship aid discovery, but the record fields retain verification and confidence information so that contextual or incompletely verified evidence is not mistaken for directly observed private credit.

## Working Paper

Han Chin Li, *Credit Under Pressure: Social Mediation, Debt Stock, and Financial Fragility in Cicero's Correspondence* (Independent Research Working Paper, version 1.0, 15 July 2026).

[Read or download the working paper (PDF)](paper/Li_2026_Credit_Under_Pressure_Working_Paper_v1.0.pdf). This is the public version associated with repository release v1.1.2. DOI registration is deferred.

## What O1-O6 Mean

| ID | Public label | Research question |
|---|---|---|
| O1 | Actor centrality by social role | Which types of people occupy important positions in the documented credit network? |
| O2 | Dependence on Cicero's archive | How much do results change when Cicero is removed as actor and archival vantage point? |
| O3 | Intermediaries and third parties | How often does credit depend on agents, friends, sureties, recommenders, or account managers? |
| O4 | Credit mechanisms and financial pressure | Which records show refinancing, repayment pressure, surety, delegated claims, account transfers, or liquidity stress? |
| O5 | Active private-credit stock in Cicero's community | How much private-credit stock is visible or modeled within the documented Cicero-centered community? |
| O6 | Wider Roman-elite comparison | How does a selected O5 handoff scale to a transparent 600-senator comparison population? |

**O5-6** is a separate borrower-side route connecting O5 evidence to O6 comparisons. It starts from high-confidence 45-44 BCE cases in which Cicero is the borrower and tests illustrative lognormal and truncated-Pareto distributions. It is not a seventh objective and is separate from the graph-respecting O5 route.

See [docs/objectives.md](docs/objectives.md) for inputs, outputs, and caveats.

## Reproduce the Release

Python 3.11 or later is sufficient; the calculation code uses the standard library.

```bash
make reproduce
make verify
make test
```

`make reproduce` rebuilds O1-O6 from canonical records and reviewed analytical authorities. Existing result files are never calculation inputs. `make verify` checks structural invariants, the paper benchmarks, and the complete sensitivity package. `make reproduce-paper-findings` additionally rebuilds and verifies every repository-backed quantitative statement and figure mapped from the paper.

## Data Layers

- `data/canonical/`: reviewed release records, schema, and source manifest.
- `data/exposure_groups/`: reviewed record-to-exposure decisions and typed analytical authorities.
- `data/amounts/`: normalized amount evidence.
- `config/`: objective labels, method versions, parameters, and reviewed O5-6 membership.
- `results/official/`: generated release results.
- `validation/`: expected release values, checksums, and verification evidence.

Canonical evidence and generated estimates are different layers. O5 and O6 values are model outputs, not canonical records or directly observed totals.

The public sensitivity exports include the 78-case distribution grid, 312-case participation grid, all 46 integer k scenarios from 5 through 50, five missing-edge probability rules, three O6 denominator policies, and nine density-discount scenarios. Their filenames and paper locations are enumerated in the paper claim map.

See [docs/paper_findings.md](docs/paper_findings.md) for the paper-to-output map, [docs/numerical_precision.md](docs/numerical_precision.md) for calculation boundaries, and [docs/source_editions.md](docs/source_editions.md) for the consulted editions.

## Contribute from a Fork

Contributors normally add a JSON proposal under `data/contributions/proposals/`; they do not edit the canonical CSV. Copy the example and assign a UUID:

```bash
cp data/contributions/examples/new-record.example.json data/contributions/proposals/my-proposal.json
make validate-proposals
make preview
```

The preview reports potentially affected objectives but does not change official results. Maintainers review the evidence, record an adjudication, assign or preserve canonical IDs, update exposure decisions where necessary, and only then rebuild an official release. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Principal Release Benchmarks

| Result | HS |
|---|---:|
| Reviewed O5 register baseline | 6,295,833.333333 |
| O5 controlled missing-edge increment | 35,307,457.374002 |
| O5 graph-respecting community stock | 41,603,290.707335 |
| O5-6 Cicero borrower-side calibration | 3,677,083.333333 |
| O6 weighted 600-senator comparison | 1,436,684,112 |

These are modeled active-stock calculations with documented assumptions. They are not aggregate Roman wealth, annual flow, or directly observed totals.

## Citation and Licenses

Use `CITATION.cff` for repository citation. The exact locally consulted primary-source editions and reprints are documented in [docs/source_editions.md](docs/source_editions.md). Code is MIT-licensed. The structured dataset is released under CC BY 4.0, subject to the separate rights that may apply to quoted editions or linked source material.
