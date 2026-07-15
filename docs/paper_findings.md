# Paper-to-output claim map

`make reproduce-paper-findings` rebuilds the complete O1–O6 release, the paper's seven sensitivity families, a machine-readable quantitative registry, and six deterministic paper-facing figures. It then verifies every repository-derived entry in `paper_findings_manifest.csv` and refreshes the release checksums.

The manifest maps paper sections and tables at the level at which they are generated or verified. A table row may therefore cover all printed cells in the named table when the complete backing CSV is the artifact. Individual headline values are also recorded in `results/official/paper_findings.csv` so that website code and independent audits do not need to scrape the paper.

Rows marked `external_citation_not_repository_derived` are deliberately outside the computational reproduction claim. They are historical comparanda taken from the cited scholarship or ancient source, and their consulted editions are documented in `source_editions.md`.

Figures are emitted as SVGs under `build/paper_findings/figures/`. They reproduce the underlying network or mechanism finding deterministically; their typography may differ from the publication layout.

The public repository does not redistribute copyrighted source editions. `data/canonical/source_manifest.csv` identifies the files consulted in the research workspace, their public URLs where available, and their explicit release status.
