#!/usr/bin/env python3
"""Build objective-specific graph findings tables for Section 11 objectives 1 and 2."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH_TABLES = ROOT / "build" / "analysis" / "graphs" / "tables"
FINDINGS = ROOT / "results" / "official" / "objectives"

CENTRALITY = GRAPH_TABLES / "graph_variant_centrality.csv"
NODES = GRAPH_TABLES / "actor_nodes.csv"
EDGES = GRAPH_TABLES / "actor_edges.csv"
VARIANT_MANIFEST = GRAPH_TABLES / "graph_variant_manifest.csv"

OBJ_01 = FINDINGS / "01_network_centrality_by_actor_type" / "tables"
OBJ_02 = FINDINGS / "02_cicero_dependence_tests" / "tables"

METRICS = ["weighted_degree", "component_size", "pagerank", "betweenness"]
UNEXPECTED_TYPES = {
    "family_or_household",
    "freedman_or_agent",
    "professional_financier",
    "civic_body",
    "public_body",
    "collective_group",
}

PAIR_DEFINITIONS = [
    {
        "variant_pair_id": "ciceronian_period_vs_cicero_removed",
        "included_variant": "ciceronian_period_graph",
        "removed_variant": "ciceronian_period_cicero_removed_graph",
        "comparison_scope": "100-40 BCE Ciceronian-period transaction-safe actor edges",
        "interpretive_use": "Main same-scope source-vantage stress test; use to identify actors and components whose prominence depends on Cicero as an archival hub within the selected Ciceronian-period graph.",
    },
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def fmt(value: float, places: int = 6) -> str:
    return f"{value:.{places}f}"


def split_values(value: str) -> list[str]:
    return [piece.strip() for piece in value.split(";") if piece.strip()]


def join_sorted(values: set[str]) -> str:
    return "; ".join(sorted(value for value in values if value))


def top_names(rows: list[dict[str, object]], metric: str, limit: int = 5) -> str:
    ordered = sorted(rows, key=lambda row: float(row.get(metric, 0) or 0), reverse=True)
    return "; ".join(f"{row['canonical_name']} ({float(row.get(metric, 0) or 0):.4g})" for row in ordered[:limit])


def index_nodes(nodes: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_name = {row["canonical_name"]: row for row in nodes}
    by_id = {row["node_id"]: row for row in nodes}
    return by_name, by_id


def enriched_centrality(
    centrality: list[dict[str, str]], nodes_by_name: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in centrality:
        node = nodes_by_name.get(row["canonical_name"], {})
        out: dict[str, object] = {
            "variant_name": row["variant_name"],
            "centrality_rank": row["centrality_rank"],
            "node_id": node.get("node_id", ""),
            "canonical_name": row["canonical_name"],
            "actor_type": node.get("actor_type", "unmatched"),
            "actor_subtype": node.get("actor_subtype", ""),
            "identity_group": node.get("identity_group", ""),
            "direct_record_count": node.get("direct_record_count", ""),
            "third_party_record_count": node.get("third_party_record_count", ""),
            "borrower_count": node.get("borrower_count", ""),
            "lender_count": node.get("lender_count", ""),
            "third_party_count": node.get("third_party_count", ""),
        }
        for metric in METRICS:
            out[metric] = as_float(row.get(metric, "0"))
        rows.append(out)
    return rows


def build_actor_type_centrality_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["variant_name"]), str(row["actor_type"]))].append(row)

    out: list[dict[str, object]] = []
    for (variant, actor_type), group in sorted(grouped.items()):
        node_count = len(group)
        metric_sums = {metric: sum(float(row[metric]) for row in group) for metric in METRICS}
        row: dict[str, object] = {
            "variant_name": variant,
            "actor_type": actor_type,
            "node_count": node_count,
            "top_nodes_by_pagerank": top_names(group, "pagerank"),
            "top_nodes_by_betweenness": top_names(group, "betweenness"),
        }
        for metric in METRICS:
            row[f"total_{metric}"] = fmt(metric_sums[metric])
            row[f"mean_{metric}"] = fmt(metric_sums[metric] / node_count if node_count else 0)
        out.append(row)
    return out


def build_top_actors_by_variant(rows: list[dict[str, object]], limit: int = 20) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["variant_name"])].append(row)

    out: list[dict[str, object]] = []
    for variant, group in sorted(grouped.items()):
        for metric in METRICS:
            ordered = sorted(group, key=lambda row: float(row[metric]), reverse=True)
            for rank, row in enumerate(ordered[:limit], start=1):
                out.append(
                    {
                        "variant_name": variant,
                        "metric": metric,
                        "metric_rank": rank,
                        "node_id": row["node_id"],
                        "canonical_name": row["canonical_name"],
                        "actor_type": row["actor_type"],
                        "value": fmt(float(row[metric])),
                        "centrality_rank": row["centrality_rank"],
                        "direct_record_count": row["direct_record_count"],
                        "third_party_record_count": row["third_party_record_count"],
                    }
                )
    return out


def build_centrality_outliers(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    out = []
    for row in rows:
        weighted_degree = float(row["weighted_degree"])
        pagerank = float(row["pagerank"])
        betweenness = float(row["betweenness"])
        actor_type = str(row["actor_type"])
        flags = []
        if actor_type in UNEXPECTED_TYPES and (weighted_degree >= 5 or pagerank >= 0.01 or betweenness >= 0.01):
            flags.append("unexpected_actor_type_high_centrality")
        if as_int(str(row["third_party_record_count"])) > as_int(str(row["direct_record_count"])):
            flags.append("third_party_prominence_exceeds_direct_party_count")
        if not flags:
            continue
        out.append(
            {
                "variant_name": row["variant_name"],
                "node_id": row["node_id"],
                "canonical_name": row["canonical_name"],
                "actor_type": actor_type,
                "weighted_degree": fmt(weighted_degree),
                "pagerank": fmt(pagerank),
                "betweenness": fmt(betweenness),
                "direct_record_count": row["direct_record_count"],
                "third_party_record_count": row["third_party_record_count"],
                "review_flags": "; ".join(flags),
            }
        )
    return sorted(out, key=lambda row: (row["variant_name"], -as_float(str(row["pagerank"]))))


def build_actor_type_mechanism_summary(
    edges: list[dict[str, str]], nodes_by_id: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for edge in edges:
        for endpoint in ["source_id", "target_id"]:
            node = nodes_by_id.get(edge[endpoint], {})
            actor_type = node.get("actor_type", "unmatched")
            key = (
                actor_type,
                edge["mechanism_type"],
                edge["analysis_loan_type"],
                edge["scope_type"],
            )
            if key not in grouped:
                grouped[key] = {
                    "actor_type": actor_type,
                    "mechanism_type": edge["mechanism_type"],
                    "analysis_loan_type": edge["analysis_loan_type"],
                    "scope_type": edge["scope_type"],
                    "edge_count": 0,
                    "direct_edge_count": 0,
                    "third_party_context_edge_count": 0,
                    "actors": Counter(),
                    "records": set(),
                    "date_periods": set(),
                    "confidence_values": set(),
                }
            bucket = grouped[key]
            bucket["edge_count"] = int(bucket["edge_count"]) + 1
            if edge["layer"] == "direct_financial":
                bucket["direct_edge_count"] = int(bucket["direct_edge_count"]) + 1
            if edge["layer"] == "third_party_context":
                bucket["third_party_context_edge_count"] = int(bucket["third_party_context_edge_count"]) + 1
            bucket["actors"][node.get("canonical_name", edge[endpoint])] += 1
            bucket["records"].update(split_values(edge["records"]))
            bucket["date_periods"].add(edge["date_period"])
            bucket["confidence_values"].update(split_values(edge["confidence_values"]))

    out: list[dict[str, object]] = []
    for bucket in grouped.values():
        actors = bucket["actors"]
        out.append(
            {
                "actor_type": bucket["actor_type"],
                "mechanism_type": bucket["mechanism_type"],
                "analysis_loan_type": bucket["analysis_loan_type"],
                "scope_type": bucket["scope_type"],
                "edge_count": bucket["edge_count"],
                "direct_edge_count": bucket["direct_edge_count"],
                "third_party_context_edge_count": bucket["third_party_context_edge_count"],
                "actor_count": len(actors),
                "record_count": len(bucket["records"]),
                "top_actors": "; ".join(f"{name} ({count})" for name, count in actors.most_common(5)),
                "date_periods": join_sorted(bucket["date_periods"]),
                "confidence_values": join_sorted(bucket["confidence_values"]),
            }
        )
    return sorted(
        out,
        key=lambda row: (
            str(row["actor_type"]),
            str(row["mechanism_type"]),
            -int(row["edge_count"]),
        ),
    )


def build_actor_type_scope_summary(
    edges: list[dict[str, str]], nodes_by_id: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for edge in edges:
        for endpoint in ["source_id", "target_id"]:
            node = nodes_by_id.get(edge[endpoint], {})
            actor_type = node.get("actor_type", "unmatched")
            key = (actor_type, edge["scope_type"])
            if key not in grouped:
                grouped[key] = {
                    "actor_type": actor_type,
                    "scope_type": edge["scope_type"],
                    "edge_count": 0,
                    "direct_edge_count": 0,
                    "third_party_context_edge_count": 0,
                    "actors": Counter(),
                    "records": set(),
                    "mechanisms": Counter(),
                    "loan_types": Counter(),
                }
            bucket = grouped[key]
            bucket["edge_count"] = int(bucket["edge_count"]) + 1
            if edge["layer"] == "direct_financial":
                bucket["direct_edge_count"] = int(bucket["direct_edge_count"]) + 1
            if edge["layer"] == "third_party_context":
                bucket["third_party_context_edge_count"] = int(bucket["third_party_context_edge_count"]) + 1
            bucket["actors"][node.get("canonical_name", edge[endpoint])] += 1
            bucket["records"].update(split_values(edge["records"]))
            bucket["mechanisms"][edge["mechanism_type"]] += 1
            bucket["loan_types"][edge["analysis_loan_type"]] += 1

    out: list[dict[str, object]] = []
    for bucket in grouped.values():
        out.append(
            {
                "actor_type": bucket["actor_type"],
                "scope_type": bucket["scope_type"],
                "edge_count": bucket["edge_count"],
                "direct_edge_count": bucket["direct_edge_count"],
                "third_party_context_edge_count": bucket["third_party_context_edge_count"],
                "actor_count": len(bucket["actors"]),
                "record_count": len(bucket["records"]),
                "top_actors": "; ".join(f"{name} ({count})" for name, count in bucket["actors"].most_common(5)),
                "top_mechanisms": "; ".join(
                    f"{name} ({count})" for name, count in bucket["mechanisms"].most_common(5)
                ),
                "top_analysis_loan_types": "; ".join(
                    f"{name} ({count})" for name, count in bucket["loan_types"].most_common(5)
                ),
            }
        )
    return sorted(out, key=lambda row: (str(row["actor_type"]), str(row["scope_type"])))


def build_variant_pairs(manifest: list[dict[str, str]]) -> list[dict[str, object]]:
    manifest_by_variant = {row["variant_name"]: row for row in manifest}
    out = []
    for pair in PAIR_DEFINITIONS:
        included = manifest_by_variant[pair["included_variant"]]
        removed = manifest_by_variant[pair["removed_variant"]]
        out.append(
            {
                **pair,
                "included_node_count": included["node_count"],
                "removed_node_count": removed["node_count"],
                "included_edge_count": included["edge_count"],
                "removed_edge_count": removed["edge_count"],
                "included_record_count": included["record_count"],
                "removed_record_count": removed["record_count"],
            }
        )
    return out


def build_centrality_delta(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_variant_name = {(str(row["variant_name"]), str(row["canonical_name"])): row for row in rows}
    out = []
    for pair in PAIR_DEFINITIONS:
        names = {
            name
            for variant, name in by_variant_name
            if variant in {pair["included_variant"], pair["removed_variant"]}
        }
        for name in sorted(names):
            with_row = by_variant_name.get((pair["included_variant"], name), {})
            without_row = by_variant_name.get((pair["removed_variant"], name), {})
            actor_type = str((with_row or without_row).get("actor_type", ""))
            presence_status = "present_in_both"
            if with_row and not without_row:
                presence_status = "with_cicero_only"
            elif without_row and not with_row:
                presence_status = "without_cicero_only"
            for metric in METRICS:
                with_value = float(with_row[metric]) if with_row else None
                without_value = float(without_row[metric]) if without_row else None
                delta = without_value - with_value if with_value is not None and without_value is not None else None
                percent_delta = (
                    (delta / with_value * 100)
                    if delta is not None and with_value not in {None, 0.0}
                    else None
                )
                out.append(
                    {
                        "variant_pair_id": pair["variant_pair_id"],
                        "node_id": (with_row or without_row).get("node_id", ""),
                        "canonical_name": name,
                        "actor_type": actor_type,
                        "present_with_cicero": "yes" if with_row else "no",
                        "present_without_cicero": "yes" if without_row else "no",
                        "presence_status": presence_status,
                        "metric": metric,
                        "value_with_cicero": fmt(with_value) if with_value is not None else "",
                        "value_without_cicero": fmt(without_value) if without_value is not None else "",
                        "absolute_delta": fmt(delta) if delta is not None else "",
                        "percent_delta": fmt(percent_delta, 2) if percent_delta is not None else "",
                        "rank_with_cicero": with_row.get("centrality_rank", ""),
                        "rank_without_cicero": without_row.get("centrality_rank", ""),
                        "rank_delta": as_int(str(without_row.get("centrality_rank", "0")))
                        - as_int(str(with_row.get("centrality_rank", "0")))
                        if with_row and without_row
                        else "",
                    }
                )
    return out


def build_component_delta(manifest: list[dict[str, str]]) -> list[dict[str, object]]:
    manifest_by_variant = {row["variant_name"]: row for row in manifest}
    out = []
    for pair in PAIR_DEFINITIONS:
        included = manifest_by_variant[pair["included_variant"]]
        removed = manifest_by_variant[pair["removed_variant"]]
        out.append(
            {
                "variant_pair_id": pair["variant_pair_id"],
                "included_variant": pair["included_variant"],
                "removed_variant": pair["removed_variant"],
                "component_count_with_cicero": included["component_count"],
                "component_count_without_cicero": removed["component_count"],
                "component_count_delta": as_int(removed["component_count"]) - as_int(included["component_count"]),
                "largest_component_with_cicero": included["largest_component_node_count"],
                "largest_component_without_cicero": removed["largest_component_node_count"],
                "largest_component_delta": as_int(removed["largest_component_node_count"])
                - as_int(included["largest_component_node_count"]),
                "node_count_delta": as_int(removed["node_count"]) - as_int(included["node_count"]),
                "edge_count_delta": as_int(removed["edge_count"]) - as_int(included["edge_count"]),
                "record_count_delta": as_int(removed["record_count"]) - as_int(included["record_count"]),
                "top_nodes_with_cicero": included["top_weighted_degree_nodes"],
                "top_nodes_without_cicero": removed["top_weighted_degree_nodes"],
            }
        )
    return out


def build_sensitive_actors(delta_rows: list[dict[str, object]], limit: int = 50) -> list[dict[str, object]]:
    pagerank_rows = [
        row
        for row in delta_rows
        if row["metric"] == "pagerank"
        and row["canonical_name"] != "Cicero"
        and row.get("presence_status") == "present_in_both"
    ]
    ordered = sorted(pagerank_rows, key=lambda row: abs(as_float(str(row["absolute_delta"]))), reverse=True)
    return ordered[:limit]


def build_robustness_summary(
    variant_pairs: list[dict[str, object]], component_delta: list[dict[str, object]], sensitive: list[dict[str, object]]
) -> list[dict[str, object]]:
    out = []
    component_by_pair = {row["variant_pair_id"]: row for row in component_delta}
    sensitive_by_pair: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in sensitive:
        sensitive_by_pair[str(row["variant_pair_id"])].append(row)
    for pair in variant_pairs:
        pair_id = str(pair["variant_pair_id"])
        component = component_by_pair[pair_id]
        actors = sensitive_by_pair[pair_id][:10]
        out.append(
            {
                "variant_pair_id": pair_id,
                "comparison_scope": pair["comparison_scope"],
                "interpretive_use": pair["interpretive_use"],
                "component_count_delta": component["component_count_delta"],
                "largest_component_delta": component["largest_component_delta"],
                "edge_count_delta": component["edge_count_delta"],
                "most_sensitive_actors_by_pagerank_delta": "; ".join(
                    f"{row['canonical_name']} ({row['absolute_delta']})" for row in actors
                ),
                "caveat": "This is a source-vantage robustness control, not evidence that the surviving archive maps objective social importance.",
            }
        )
    return out


def main() -> None:
    nodes = load_rows(NODES)
    edges = load_rows(EDGES)
    centrality = load_rows(CENTRALITY)
    manifest = load_rows(VARIANT_MANIFEST)
    nodes_by_name, nodes_by_id = index_nodes(nodes)
    enriched = enriched_centrality(centrality, nodes_by_name)

    write_rows(
        OBJ_01 / "actor_type_centrality_summary.csv",
        [
            "variant_name",
            "actor_type",
            "node_count",
            "total_weighted_degree",
            "mean_weighted_degree",
            "total_component_size",
            "mean_component_size",
            "total_pagerank",
            "mean_pagerank",
            "total_betweenness",
            "mean_betweenness",
            "top_nodes_by_pagerank",
            "top_nodes_by_betweenness",
        ],
        build_actor_type_centrality_summary(enriched),
    )
    write_rows(
        OBJ_01 / "actor_type_mechanism_summary.csv",
        [
            "actor_type",
            "mechanism_type",
            "analysis_loan_type",
            "scope_type",
            "edge_count",
            "direct_edge_count",
            "third_party_context_edge_count",
            "actor_count",
            "record_count",
            "top_actors",
            "date_periods",
            "confidence_values",
        ],
        build_actor_type_mechanism_summary(edges, nodes_by_id),
    )
    write_rows(
        OBJ_01 / "actor_type_scope_summary.csv",
        [
            "actor_type",
            "scope_type",
            "edge_count",
            "direct_edge_count",
            "third_party_context_edge_count",
            "actor_count",
            "record_count",
            "top_actors",
            "top_mechanisms",
            "top_analysis_loan_types",
        ],
        build_actor_type_scope_summary(edges, nodes_by_id),
    )
    write_rows(
        OBJ_01 / "top_actors_by_variant.csv",
        [
            "variant_name",
            "metric",
            "metric_rank",
            "node_id",
            "canonical_name",
            "actor_type",
            "value",
            "centrality_rank",
            "direct_record_count",
            "third_party_record_count",
        ],
        build_top_actors_by_variant(enriched),
    )
    write_rows(
        OBJ_01 / "centrality_outliers_for_review.csv",
        [
            "variant_name",
            "node_id",
            "canonical_name",
            "actor_type",
            "weighted_degree",
            "pagerank",
            "betweenness",
            "direct_record_count",
            "third_party_record_count",
            "review_flags",
        ],
        build_centrality_outliers(enriched),
    )

    variant_pairs = build_variant_pairs(manifest)
    centrality_delta = build_centrality_delta(enriched)
    component_delta = build_component_delta(manifest)
    sensitive = build_sensitive_actors(centrality_delta)

    write_rows(
        OBJ_02 / "cicero_dependence_variant_pairs.csv",
        [
            "variant_pair_id",
            "included_variant",
            "removed_variant",
            "comparison_scope",
            "interpretive_use",
            "included_node_count",
            "removed_node_count",
            "included_edge_count",
            "removed_edge_count",
            "included_record_count",
            "removed_record_count",
        ],
        variant_pairs,
    )
    write_rows(
        OBJ_02 / "centrality_delta_with_without_cicero.csv",
        [
            "variant_pair_id",
            "node_id",
            "canonical_name",
            "actor_type",
            "present_with_cicero",
            "present_without_cicero",
            "presence_status",
            "metric",
            "value_with_cicero",
            "value_without_cicero",
            "absolute_delta",
            "percent_delta",
            "rank_with_cicero",
            "rank_without_cicero",
            "rank_delta",
        ],
        centrality_delta,
    )
    write_rows(
        OBJ_02 / "component_delta_with_without_cicero.csv",
        [
            "variant_pair_id",
            "included_variant",
            "removed_variant",
            "component_count_with_cicero",
            "component_count_without_cicero",
            "component_count_delta",
            "largest_component_with_cicero",
            "largest_component_without_cicero",
            "largest_component_delta",
            "node_count_delta",
            "edge_count_delta",
            "record_count_delta",
            "top_nodes_with_cicero",
            "top_nodes_without_cicero",
        ],
        component_delta,
    )
    write_rows(
        OBJ_02 / "actors_most_sensitive_to_cicero_removal.csv",
        [
            "variant_pair_id",
            "node_id",
            "canonical_name",
            "actor_type",
            "present_with_cicero",
            "present_without_cicero",
            "presence_status",
            "metric",
            "value_with_cicero",
            "value_without_cicero",
            "absolute_delta",
            "percent_delta",
            "rank_with_cicero",
            "rank_without_cicero",
            "rank_delta",
        ],
        sensitive,
    )
    write_rows(
        OBJ_02 / "robustness_summary.csv",
        [
            "variant_pair_id",
            "comparison_scope",
            "interpretive_use",
            "component_count_delta",
            "largest_component_delta",
            "edge_count_delta",
            "most_sensitive_actors_by_pagerank_delta",
            "caveat",
        ],
        build_robustness_summary(variant_pairs, component_delta, sensitive),
    )


if __name__ == "__main__":
    main()
