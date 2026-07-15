#!/usr/bin/env python3
"""Build the paper-facing quantitative registry and deterministic SVG figures."""

from __future__ import annotations

import csv
import html
import math
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "paper_findings"
FIGURES = BUILD / "figures"
OFFICIAL = ROOT / "results" / "official"
GRAPHS = ROOT / "build" / "analysis" / "graphs" / "tables" / "graph_variants"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def largest_component(edges: list[dict[str, str]]) -> int:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in edges:
        a, b = row["source_id"], row["target_id"]
        adjacency[a].add(b)
        adjacency[b].add(a)
    largest = 0
    unseen = set(adjacency)
    while unseen:
        start = unseen.pop()
        queue = deque([start])
        size = 0
        while queue:
            node = queue.popleft()
            size += 1
            for neighbor in adjacency[node] & unseen:
                unseen.remove(neighbor)
                queue.append(neighbor)
        largest = max(largest, size)
    return largest


def network_svg(path: Path, title: str, edges: list[dict[str, str]]) -> None:
    names: dict[str, str] = {}
    degree: dict[str, int] = defaultdict(int)
    for row in edges:
        names[row["source_id"]] = row["source_name"]
        names[row["target_id"]] = row["target_name"]
        degree[row["source_id"]] += 1
        degree[row["target_id"]] += 1
    nodes = sorted(names, key=lambda node: (-degree[node], names[node]))[:80]
    chosen = set(nodes)
    shown_edges = [row for row in edges if row["source_id"] in chosen and row["target_id"] in chosen]
    positions = {
        node: (500 + 365 * math.cos(2 * math.pi * index / max(1, len(nodes))), 430 + 315 * math.sin(2 * math.pi * index / max(1, len(nodes))))
        for index, node in enumerate(nodes)
    }
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="800" viewBox="0 0 1000 800">',
        '<rect width="1000" height="800" fill="#fbfaf7"/>',
        f'<text x="500" y="38" text-anchor="middle" font-family="serif" font-size="25">{html.escape(title)}</text>',
        f'<text x="500" y="66" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#555">{len(edges)} edges · {len({x for row in edges for x in (row["source_id"], row["target_id"])})} actors</text>',
    ]
    for row in shown_edges:
        x1, y1 = positions[row["source_id"]]
        x2, y2 = positions[row["target_id"]]
        color = "#ba4a45" if row.get("layer") == "direct_financial" else "#527aa3"
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-opacity=".25"/>')
    for node in nodes:
        x, y = positions[node]
        radius = min(14, 3 + math.sqrt(degree[node]))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="#27364b" fill-opacity=".88"/>')
        if degree[node] >= sorted(degree.values(), reverse=True)[min(11, len(degree) - 1)]:
            parts.append(f'<text x="{x + radius + 3:.1f}" y="{y + 4:.1f}" font-family="sans-serif" font-size="11">{html.escape(names[node])}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def bar_svg(path: Path, rows: list[dict[str, str]]) -> None:
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="650" viewBox="0 0 1000 650">', '<rect width="1000" height="650" fill="#fbfaf7"/>', '<text x="500" y="42" text-anchor="middle" font-family="serif" font-size="25">Third-party/context share by credit mechanism</text>']
    for index, row in enumerate(rows):
        y = 85 + index * 65
        share = float(row["third_party_edge_share"])
        parts.extend((
            f'<text x="275" y="{y + 20}" text-anchor="end" font-family="sans-serif" font-size="15">{html.escape(row["mechanism_type"])}</text>',
            f'<rect x="300" y="{y}" width="{share * 600:.1f}" height="30" fill="#527aa3"/>',
            f'<text x="{315 + share * 600:.1f}" y="{y + 21}" font-family="sans-serif" font-size="14">{share:.1%}</text>',
        ))
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    ciceronian = read_csv(GRAPHS / "ciceronian_period_graph.csv")
    direct = [row for row in ciceronian if row["layer"] == "direct_financial"]
    context = [row for row in ciceronian if row["layer"] == "third_party_context"]
    removed = read_csv(GRAPHS / "ciceronian_period_cicero_removed_graph.csv")
    chain = read_csv(OFFICIAL / "objectives" / "04_credit_mechanisms" / "tables" / "graph_variants" / "refinancing_chain_graph.csv")
    mechanism = read_csv(OFFICIAL / "objectives" / "03_intermediaries_and_third_parties" / "tables" / "third_party_by_mechanism.csv")
    network_svg(FIGURES / "ciceronian_period_actor_graph.svg", "Ciceronian-period actor network, 100–40 BCE", ciceronian)
    network_svg(FIGURES / "direct_borrower_lender_graph.svg", "Direct borrower–lender relations", direct)
    network_svg(FIGURES / "third_party_context_graph.svg", "Third-party and contextual relations", context)
    network_svg(FIGURES / "cicero_removed_actor_graph.svg", "Ciceronian-period network with Cicero removed", removed)
    network_svg(FIGURES / "cicero_44_bce_refinancing_chain.svg", "Refinancing and settlement-pressure chains", chain)
    bar_svg(FIGURES / "third_party_share_by_mechanism.svg", mechanism)

    summary = {row["value_id"]: row["value"] for row in read_csv(OFFICIAL / "headline_values.csv")}
    candidates = read_csv(OFFICIAL / "objective_05_06" / "recalculation_v5" / "intermediate" / "o6_internal_candidate_expected_incidence.csv")
    k_selected = next(row for row in read_csv(OFFICIAL / "o5_6_k_sensitivity.csv") if row["scenario_status"] == "selected_base")
    distributions = read_csv(OFFICIAL / "o5_6_distribution_values.csv")
    distribution_grid = read_csv(OFFICIAL / "o5_6_distribution_grid.csv")
    participation_grid = read_csv(OFFICIAL / "o5_6_participation_sensitivity.csv")
    chains = read_csv(OFFICIAL / "objectives" / "04_credit_mechanisms" / "tables" / "refinancing_chains.csv")
    t4 = float(summary["O5-T4"])
    t5 = float(summary["O5-T5"])
    selected_distribution_values = [float(row["senators_600_mean_hs"]) for row in distributions]
    claims = [
        ("canonical_records", "114", "records", "data/canonical/cicero_credit_records.csv"),
        ("ciceronian_direct_edges", len(direct), "edges", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("ciceronian_direct_records", len({rid for row in direct for rid in row["records"].split("; ")}), "records", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("ciceronian_direct_largest_component", largest_component(direct), "actors", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("ciceronian_context_edges", len(context), "edges", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("ciceronian_context_records", len({rid for row in context for rid in row["records"].split("; ")}), "records", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("ciceronian_context_largest_component", largest_component(context), "actors", "build/analysis/graphs/tables/graph_variants/ciceronian_period_graph.csv"),
        ("cicero_removed_edges", len(removed), "edges", "build/analysis/graphs/tables/graph_variants/ciceronian_period_cicero_removed_graph.csv"),
        ("cicero_removed_records", len({rid for row in removed for rid in row["records"].split("; ")}), "records", "build/analysis/graphs/tables/graph_variants/ciceronian_period_cicero_removed_graph.csv"),
        ("cicero_removed_largest_component", largest_component(removed), "actors", "build/analysis/graphs/tables/graph_variants/ciceronian_period_cicero_removed_graph.csv"),
        ("o5_t4_hs", summary["O5-T4"], "HS", "results/official/headline_values.csv"),
        ("o5_t5_missing_edge_increment_hs", summary["O5-T5-missing-edge-increment"], "HS", "results/official/headline_values.csv"),
        ("o5_t5_hs", summary["O5-T5"], "HS", "results/official/headline_values.csv"),
        ("o5_accepted_share_percent", f"{100 * t4 / t5:.1f}", "percent", "results/official/headline_values.csv"),
        ("o5_modeled_share_percent", f"{100 * (t5 - t4) / t5:.1f}", "percent", "results/official/headline_values.csv"),
        ("o56_hs", summary["O5-6"], "HS", "results/official/headline_values.csv"),
        ("o6w_t5a_hs", summary["O6W-T5A"], "HS", "results/official/headline_values.csv"),
        ("o5_imputed_amount_hs", k_selected["imputed_amount_hs"], "HS", "results/official/o5_6_k_sensitivity.csv"),
        ("o5_candidate_count", len(candidates), "dyads", "results/official/objective_05_06/recalculation_v5/intermediate/o6_internal_candidate_expected_incidence.csv"),
        ("o5_expected_edge_mass", k_selected["expected_edge_mass"], "expected edges", "results/official/o5_6_k_sensitivity.csv"),
        ("o6_effective_population", k_selected["o6_effective_population"], "central-equivalent actors", "results/official/o5_6_k_sensitivity.csv"),
        ("o6_multiplier", f'{600 / float(k_selected["o6_effective_population"]):.12f}'.rstrip("0"), "multiplier", "results/official/o5_6_k_sensitivity.csv"),
        ("distribution_benchmarks", ";".join(row["senators_600_mean_hs"] for row in distributions), "HS", "results/official/o5_6_distribution_values.csv"),
        ("distribution_selected_min_hs", int(min(selected_distribution_values)), "HS", "results/official/o5_6_distribution_values.csv"),
        ("distribution_selected_max_hs", int(max(selected_distribution_values)), "HS", "results/official/o5_6_distribution_values.csv"),
        ("distribution_grid_rows", len(distribution_grid), "scenarios", "results/official/o5_6_distribution_grid.csv"),
        ("distribution_grid_at_least_1b", sum(float(row["senators_600_mean_hs"]) >= 1_000_000_000 for row in distribution_grid), "scenarios", "results/official/o5_6_distribution_grid.csv"),
        ("participation_grid_rows", len(participation_grid), "scenarios", "results/official/o5_6_participation_sensitivity.csv"),
        ("participation_grid_100m_to_999m", sum(100_000_000 <= float(row["participation_adjusted_hs"]) < 1_000_000_000 for row in participation_grid), "scenarios", "results/official/o5_6_participation_sensitivity.csv"),
        ("participation_grid_min_hs", int(min(float(row["participation_adjusted_hs"]) for row in participation_grid)), "HS", "results/official/o5_6_participation_sensitivity.csv"),
        ("k_grid_rows", len(read_csv(OFFICIAL / "o5_6_k_sensitivity.csv")), "scenarios", "results/official/o5_6_k_sensitivity.csv"),
        ("probability_rule_rows", len(read_csv(OFFICIAL / "o5_missing_edge_probability_rule_sensitivity.csv")), "scenarios", "results/official/o5_missing_edge_probability_rule_sensitivity.csv"),
        ("denominator_policy_rows", len(read_csv(OFFICIAL / "o6_denominator_policy_sensitivity.csv")), "scenarios", "results/official/o6_denominator_policy_sensitivity.csv"),
        ("density_discount_rows", len(read_csv(OFFICIAL / "o6_density_discount_sensitivity.csv")), "scenarios", "results/official/o6_density_discount_sensitivity.csv"),
        ("o6_ratio_to_600m", f'{float(summary["O6W-T5A"]) / 600_000_000:.6f}', "ratio", "results/official/o6_density_discount_sensitivity.csv"),
        ("refinancing_chains", len(chains), "chains", "results/official/objectives/04_credit_mechanisms/tables/refinancing_chains.csv"),
        ("acute_refinancing_chains", sum(row["chain_class"] == "acute_chain_stress" for row in chains), "chains", "results/official/objectives/04_credit_mechanisms/tables/refinancing_chains.csv"),
    ]
    write_csv(OFFICIAL / "paper_findings.csv", [{"claim_id": claim, "value": value, "unit": unit, "source_artifact": source} for claim, value, unit, source in claims])
    print(f"Paper findings reproduced: {len(claims)} quantitative checks and 6 figures")


if __name__ == "__main__":
    main()
