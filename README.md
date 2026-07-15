# Credit Under Pressure

**Independent Research Project**

**Working Paper v1.0**

**Current status:** Under external academic review.

*Credit Under Pressure: Social Mediation, Debt Stock, and Financial Fragility in Cicero's Correspondence* examines private credit, social position, intermediation, and modeled financial exposure in the late Roman Republic. This repository contains the working paper, reviewed research data, and the code used to reproduce its quantitative findings.

## Paper

**Han Chin Li**, *Credit Under Pressure: Social Mediation, Debt Stock, and Financial Fragility in Cicero's Correspondence*. Independent Research Working Paper, version 1.0, 15 July 2026.

- [Read or download Working Paper v1.0 (PDF)](paper/Li_2026_Credit_Under_Pressure_Working_Paper_v1.0.pdf)
- [Visit the paper's website](https://hcl-1024.github.io/systems-across-time/research/paper.html)
- [View paper-to-output documentation](docs/paper_findings.md)

## Data

The current release contains 114 reviewed canonical records. Latin is the control text. Translations, OCR, and secondary scholarship support discovery, while verification and confidence fields distinguish directly observed evidence from contextual or incompletely verified material.

- [Canonical dataset](data/canonical/)
- [Data dictionary](data/canonical/data_dictionary.md)
- [Exposure-group authorities](data/exposure_groups/)
- [Normalized amount evidence](data/amounts/)
- [Official generated results](results/official/)
- [Source editions](docs/source_editions.md)

Canonical evidence and generated estimates are separate data layers. O5 and O6 are modeled active-stock calculations, not directly observed ancient totals, aggregate Roman wealth, or annual credit flows.

## Code

Python 3.11 or later is sufficient. The calculation code uses the standard library.

```bash
make reproduce
make verify
make test
make reproduce-paper-findings
```

`make reproduce` rebuilds O1–O6 from the canonical records and reviewed analytical authorities. `make verify` checks structural invariants, paper benchmarks, and the complete sensitivity package. `make reproduce-paper-findings` rebuilds and verifies every repository-backed quantitative statement and figure mapped from the paper.

- [Objective definitions and caveats](docs/objectives.md)
- [Paper claim map](docs/paper_findings.md)
- [Numerical-precision policy](docs/numerical_precision.md)
- [Calculation source code](src/)
- [Automated tests](tests/)

## Version history

| Research object | Version | Date | Status |
|---|---:|---|---|
| Working paper | 1.0 | 15 July 2026 | Under external academic review |
| Data and code repository | 1.1.2 | 15 July 2026 | Current public release |

See the [complete changelog](CHANGELOG.md) for earlier repository releases.

Use [`CITATION.cff`](CITATION.cff) when citing the data and code repository. Code is MIT-licensed, and the structured dataset is released under CC BY 4.0, subject to the separate rights that may apply to quoted editions or linked source material.
