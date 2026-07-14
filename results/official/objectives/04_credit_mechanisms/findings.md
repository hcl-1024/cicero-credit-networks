# Objective 04: Credit Mechanisms

## Research Question

Which Cicero/Verboven credit records and episode-level chains show liquidity stress, refinancing pressure, repayment pressure, account-based liquidity management, surety pressure, or third-party-dependent stress?

## Dataset And Filters

The headline denominator is the broad canonical dataset: 114 records. Strict sensitivity uses Ciceronian-period, Latin-controlled, high-confidence, private/household rows.

Generated Objective 04 tables are in `tables/`, with stress-specific and chain-specific graph variants in `tables/graph_variants/`.

## Methods And Controls

Each canonical record receives a 0-5 liquidity-stress score. Explicit refinancing or *versura* contributes 3 points; repayment pressure, overdue/disputed status, or urgent collection language contributes 2 points; account/nomina, surety, or third-party context contributes 1 point. Scores are capped at 5.

The refinancing-chain layer groups qualifying stress records by episode. Chain scoring asks whether an episode combines explicit *versura*/refinancing, failed or uncertain expected payment, sale fallback, account/nomina transfer, surety/security, third-party intermediation, and repeated attestation across records or letters. This chain score is a transparent research coding device, not an ancient category.

Actor rankings are role-specific: borrowers/debtors, lenders/creditors, intermediaries, and all-role visibility are reported separately.

## Key Findings

1. 92 of 114 canonical records have at least one liquidity-stress signal; 8 are high-stress records with score >= 4.
2. Refinancing/versura appears in 10 stress records, while repayment pressure appears in 28 stress records. These categories overlap in some cases but should remain analytically distinct.
3. The strict sensitivity slice contains 21 stress records and 4 high-stress records.
4. Top high-stress borrowers/debtors by preserved record count: Cicero (3); Quintus Cicero (1); Dolabella (1); L. Tullius Montanus (1); Heraclides (1).
5. Top high-stress lenders/creditors by preserved record count: Cicero (1); Atticus (1); C. Fufius (1); Egnatius (1); M. Fufius (1).
6. Top high-stress intermediaries/context actors by preserved record count: Atticus (3); Cicero (1); Tiro (1); Eros (1); Terentia (1).
7. 17 episode-level refinancing/liquidity chains are reconstructed in `tables/refinancing_chains.csv`; 8 are significant or acute chain-stress cases, and 7 are acute under the chain score.
8. Highest-scoring chain episodes: Att. 16.6 Cluvian-Publilius-Terentia cluster (9, acute_chain_stress); Dolabella debt/account thread (9, acute_chain_stress); Philotimus/Philogenes accounts (9, acute_chain_stress); Quintus debt thread (9, acute_chain_stress); Tiro/domestic accounts (9, acute_chain_stress).

## Evidence Table

| Claim | Record IDs | Output/Table | Confidence | Caveat |
|---|---|---|---|---|
| Refinancing/versura is a distinct high-pressure subset. | Aggregate record result | `tables/liquidity_stress_records.csv`; `tables/liquidity_stress_by_mechanism.csv` | Medium | Mechanism labels need Latin checking for major examples. |
| Repayment pressure is analytically separate from refinancing pressure. | Aggregate record result | `tables/liquidity_stress_records.csv` | Medium | Some records combine repayment pressure with other stress mechanisms. |
| Account/nomina and surety often mark indirect liquidity management. | Aggregate record and intermediary result | `tables/liquidity_stress_records.csv`; `tables/liquidity_stress_by_intermediary.csv` | Medium | Mechanism coding does not prove legal priority or cash movement. |
| High-stress credit episodes are strongly relational and context-mediated. | Aggregate graph result | `tables/graph_variants/stress_context_graph.csv`; `tables/liquidity_stress_graph_centrality.csv` | Medium | Graph structure reflects surviving evidence and current actor parsing. |
| Borrower, lender, and intermediary rankings tell different stories. | Aggregate actor-ranking result | `tables/liquidity_stress_by_borrower.csv`; `tables/liquidity_stress_by_lender.csv`; `tables/liquidity_stress_by_intermediary.csv` | Medium | Counts are preserved-record visibility, not total historical exposure. |
| Refinancing and liquidity stress are best tested as chains, not isolated records. | Aggregate chain result | `tables/refinancing_chains.csv`; `tables/refinancing_chain_records.csv`; `figures/refinancing_chain_graph.svg` | Medium | Chain reconstruction is heuristic and requires Latin checking before case-study prose. |

## Interpretation

Objective 04 should be read as a mechanism analysis, not as a direct balance sheet. The most useful headline actor table is the borrower/debtor table, because it ranks actors by high-stress borrowing or debt records. Lender and intermediary tables answer different questions: who appears as creditor or pressure source, and who appears as broker, guarantor, account manager, or context actor.

The graph variants make the pressure network visible by filtering the shared actor graph to stress records, high-stress records, refinancing records, repayment-pressure records, direct-only stress edges, context-only stress edges, and the reconstructed refinancing-chain graph. Rank deltas against the full graph identify actors whose importance rises specifically in liquidity-pressure contexts. In Objective 04 visualizations, direct financial arrows are drawn from lender to borrower; context arrows retain the source-to-target direction stored in the graph table.

The chain table is the most useful place to ask whether liquidity stress was significant at a particular moment. It distinguishes simple mention of debt from episodes where one payment depends on another expected source, then falls back to *versura*, sale, account transfer, surety, or friend/agent intermediation.

## Figures

- `figures/liquidity_stress_by_mechanism.svg`: shows stress-record counts by mechanism, sourced from `tables/figure_liquidity_stress_by_mechanism_source.csv`.
- `figures/liquidity_stress_timeline.svg`: plots preserved stress, high-stress, refinancing, and repayment-pressure record counts by year, sourced from `tables/figure_liquidity_stress_timeline_source.csv`.
- `figures/high_stress_behavior_graph.svg`: full high-stress liquidity-pressure graph with a node-color legend, sourced from `tables/figure_high_stress_graph_source.csv`.
- `figures/refinancing_behavior_graph.svg`: full refinancing/versura graph with a node-color legend, sourced from `tables/figure_refinancing_behavior_graph_source.csv`.
- `figures/repayment_pressure_behavior_graph.svg`: full repayment-pressure graph with a node-color legend, sourced from `tables/figure_repayment_pressure_behavior_graph_source.csv`.
- `figures/stress_context_behavior_graph.svg`: full third-party/context graph in stress records with a node-color legend, sourced from `tables/figure_stress_context_behavior_graph_source.csv`.
- `figures/refinancing_chain_graph.svg`: reconstructed chain graph, sourced from `tables/figure_refinancing_chain_graph_source.csv`.
- `figures/refinancing_chain_intensity.svg`: chain-intensity score by episode, sourced from `tables/figure_refinancing_chain_intensity_source.csv`.
- `figures/refinancing_chains/`: individual directed graph visualizations for the five highest-scoring refinancing/liquidity chains, with source tables in `tables/refinancing_chain_figure_sources/`.

These figures visualize behavior signals, chain dependency, and graph ties. The stress and chain scores are research codes and should not be treated as ancient categories or amount estimates.

## Scholarship Control

Frame these outputs with Verboven on *amicitia*, *fides*, recommendation, and surety; Andreau on creditors, agents, and finance intermediaries; and Hollander on account-based value transfer. The stress and chain scores are transparent research coding devices, not ancient categories.

## Follow-Up

1. Latin-check the highest-scoring records before using them as prose examples.
2. Review actors with large stress-graph rank gains before making claims about individual agency.
3. Latin-check the highest-scoring chain episodes, especially those involving *versura*, sale fallback, or forced borrowing.
4. Keep amount totals secondary to Objective 05/06 scale analysis.
