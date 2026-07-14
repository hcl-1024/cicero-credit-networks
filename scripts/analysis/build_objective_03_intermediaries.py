#!/usr/bin/env python3
"""Build Objective 03 third-party/intermediary graph tables."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH_TABLES = ROOT / "build" / "analysis" / "graphs" / "tables"
OBJ_ROOT = ROOT / "results" / "official" / "objectives" / "03_intermediaries_and_third_parties"
TABLES = OBJ_ROOT / "tables"

NODES = GRAPH_TABLES / "actor_nodes.csv"
EDGES = GRAPH_TABLES / "actor_edges.csv"
MANIFEST = GRAPH_TABLES / "graph_variant_manifest.csv"


DEPENDENCE_FIELDS = [
    "node_id",
    "actor_name",
    "actor_type",
    "record_count",
    "direct_record_count",
    "third_party_record_count",
    "weighted_degree",
    "direct_edge_degree",
    "third_party_context_edge_degree",
    "total_direct_plus_context_degree",
    "third_party_dependence_ratio",
    "third_party_to_direct_degree_ratio",
    "borrower_count",
    "lender_count",
    "third_party_count",
    "confidence_values",
    "episode_groups",
]

GRAPH_SUMMARY_FIELDS = [
    "variant_name",
    "description",
    "node_count",
    "edge_count",
    "record_count",
    "component_count",
    "largest_component_node_count",
    "edges_per_record",
    "largest_component_share",
    "edge_count_vs_direct_ratio",
    "largest_component_vs_direct_ratio",
    "filter_recipe",
]

ACTOR_TYPE_FIELDS = [
    "actor_type",
    "node_count",
    "weighted_degree",
    "direct_edge_degree",
    "third_party_context_edge_degree",
    "total_direct_plus_context_degree",
    "third_party_dependence_ratio",
    "third_party_to_direct_degree_ratio",
    "top_nodes",
]

MECHANISM_FIELDS = [
    "mechanism_type",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "third_party_edge_share",
    "scope_values",
    "record_count_sum_across_scopes",
    "top_actor_examples",
]

MECHANISM_SCOPE_FIELDS = [
    "analysis_loan_type",
    "mechanism_type",
    "scope_type",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "third_party_edge_share",
    "actor_count",
    "record_count",
    "top_actors",
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


def as_int(value: str | int | float) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def split_values(value: str) -> list[str]:
    return [piece.strip() for piece in value.split(";") if piece.strip()]


def ratio(context: int, direct: int) -> tuple[str, str]:
    total = context + direct
    dependence = context / total if total else 0.0
    to_direct = context / direct if direct else float(context) if context else 0.0
    return fmt(dependence), fmt(to_direct)


def top_counts(counter: Counter[str], limit: int = 8) -> str:
    return "; ".join(f"{name} ({count})" for name, count in counter.most_common(limit))


def top_node_counts(nodes: list[dict[str, str]], limit: int = 10) -> str:
    ordered = sorted(nodes, key=lambda row: (-as_int(row["weighted_degree"]), row["canonical_name"]))
    return "; ".join(f"{row['canonical_name']} ({row['weighted_degree']})" for row in ordered[:limit])


def build_dependence(nodes: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for node in nodes:
        direct = as_int(node["direct_edge_degree"])
        context = as_int(node["context_edge_degree"])
        total = direct + context
        if total == 0:
            continue
        dependence, to_direct = ratio(context, direct)
        rows.append(
            {
                "node_id": node["node_id"],
                "actor_name": node["canonical_name"],
                "actor_type": node["actor_type"],
                "record_count": node["record_count"],
                "direct_record_count": node["direct_record_count"],
                "third_party_record_count": node["third_party_record_count"],
                "weighted_degree": node["weighted_degree"],
                "direct_edge_degree": direct,
                "third_party_context_edge_degree": context,
                "total_direct_plus_context_degree": total,
                "third_party_dependence_ratio": dependence,
                "third_party_to_direct_degree_ratio": to_direct,
                "borrower_count": node["borrower_count"],
                "lender_count": node["lender_count"],
                "third_party_count": node["third_party_count"],
                "confidence_values": node["confidence_values"],
                "episode_groups": node["episode_groups"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (-float(str(row["third_party_dependence_ratio"])), -as_int(row["total_direct_plus_context_degree"]), str(row["actor_name"])),
    )


def build_graph_summary(manifest: list[dict[str, str]]) -> list[dict[str, object]]:
    wanted = [
        "direct_borrower_lender_graph",
        "third_party_context_graph",
        "combined_transaction_graph",
        "cicero_removed_graph",
    ]
    by_variant = {row["variant_name"]: row for row in manifest}
    direct = by_variant["direct_borrower_lender_graph"]
    direct_edges = as_int(direct["edge_count"]) or 1
    direct_component = as_int(direct["largest_component_node_count"]) or 1
    rows = []
    for variant in wanted:
        row = by_variant[variant]
        node_count = as_int(row["node_count"])
        edge_count = as_int(row["edge_count"])
        record_count = as_int(row["record_count"])
        largest = as_int(row["largest_component_node_count"])
        rows.append(
            {
                "variant_name": variant,
                "description": row["description"],
                "node_count": node_count,
                "edge_count": edge_count,
                "record_count": record_count,
                "component_count": row["component_count"],
                "largest_component_node_count": largest,
                "edges_per_record": fmt(edge_count / record_count if record_count else 0),
                "largest_component_share": fmt(largest / node_count if node_count else 0),
                "edge_count_vs_direct_ratio": fmt(edge_count / direct_edges),
                "largest_component_vs_direct_ratio": fmt(largest / direct_component),
                "filter_recipe": row["filter_recipe"],
            }
        )
    return rows


def build_actor_type(nodes: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in nodes:
        if as_int(node["weighted_degree"]) > 0:
            grouped[node["actor_type"]].append(node)

    rows = []
    for actor_type, group in sorted(grouped.items()):
        direct = sum(as_int(row["direct_edge_degree"]) for row in group)
        context = sum(as_int(row["context_edge_degree"]) for row in group)
        weighted = sum(as_int(row["weighted_degree"]) for row in group)
        dependence, to_direct = ratio(context, direct)
        rows.append(
            {
                "actor_type": actor_type,
                "node_count": len(group),
                "weighted_degree": weighted,
                "direct_edge_degree": direct,
                "third_party_context_edge_degree": context,
                "total_direct_plus_context_degree": direct + context,
                "third_party_dependence_ratio": dependence,
                "third_party_to_direct_degree_ratio": to_direct,
                "top_nodes": top_node_counts(group),
            }
        )
    return sorted(rows, key=lambda row: -as_int(row["weighted_degree"]))


def mechanism_group_rows(edges: list[dict[str, str]], group_fields: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], dict[str, object]] = {}
    for edge in edges:
        key = tuple(edge[field] for field in group_fields)
        item = grouped.setdefault(
            key,
            {
                **{field: edge[field] for field in group_fields},
                "edge_count": 0,
                "direct_edge_count": 0,
                "third_party_context_edge_count": 0,
                "actors": Counter(),
                "records": set(),
                "scopes": set(),
            },
        )
        weight = as_int(edge["weight"]) or 1
        item["edge_count"] = as_int(item["edge_count"]) + weight
        if edge["layer"] == "third_party_context":
            item["third_party_context_edge_count"] = as_int(item["third_party_context_edge_count"]) + weight
        else:
            item["direct_edge_count"] = as_int(item["direct_edge_count"]) + weight
        item["actors"].update({edge["source_name"]: weight, edge["target_name"]: weight})  # type: ignore[union-attr]
        item["records"].update(split_values(edge["records"]))  # type: ignore[union-attr]
        item["scopes"].add(edge["scope_type"])  # type: ignore[union-attr]

    rows = []
    for item in grouped.values():
        direct = as_int(item["direct_edge_count"])
        context = as_int(item["third_party_context_edge_count"])
        edge_count = as_int(item["edge_count"])
        base = {
            "edge_count": edge_count,
            "direct_edge_count": direct,
            "third_party_context_edge_count": context,
            "third_party_edge_share": fmt(context / edge_count if edge_count else 0),
            "actor_count": len(item["actors"]),
            "record_count": len(item["records"]),
            "top_actors": top_counts(item["actors"]),  # type: ignore[arg-type]
            "scope_values": "; ".join(sorted(item["scopes"])),  # type: ignore[arg-type]
            "record_count_sum_across_scopes": len(item["records"]),
            "top_actor_examples": top_counts(item["actors"]),  # type: ignore[arg-type]
        }
        rows.append({**{field: item[field] for field in group_fields}, **base})
    return sorted(rows, key=lambda row: (-as_int(row["edge_count"]), str(row.get("mechanism_type", ""))))


def write_findings(graph_rows: list[dict[str, object]], chain_note: str = "") -> None:
    direct = next(row for row in graph_rows if row["variant_name"] == "direct_borrower_lender_graph")
    context = next(row for row in graph_rows if row["variant_name"] == "third_party_context_graph")
    text = f"""# Objective 03: Intermediaries and Third Parties

Regenerated from the clean canonical dataset.

Key outputs:

- `tables/direct_vs_third_party_graph_summary.csv`
- `tables/actor_third_party_dependence.csv`
- `tables/top_third_party_dependent_actors.csv`
- `tables/third_party_by_actor_type.csv`
- `tables/third_party_by_mechanism.csv`
- `tables/third_party_by_mechanism_and_scope.csv`

Headline:

- Direct borrower-lender graph: {direct['edge_count']} edges across {direct['record_count']} records; largest component {direct['largest_component_node_count']} nodes.
- Third-party/context graph: {context['edge_count']} edges across {context['record_count']} records; largest component {context['largest_component_node_count']} nodes.
{chain_note}
"""
    OBJ_ROOT.mkdir(parents=True, exist_ok=True)
    (OBJ_ROOT / "findings.md").write_text(text, encoding="utf-8")


def main() -> None:
    nodes = load_rows(NODES)
    edges = load_rows(EDGES)
    manifest = load_rows(MANIFEST)

    dependence = build_dependence(nodes)
    graph_rows = build_graph_summary(manifest)
    actor_type_rows = build_actor_type(nodes)
    mechanism_rows = mechanism_group_rows(edges, ["mechanism_type"])
    mechanism_scope_rows = mechanism_group_rows(edges, ["analysis_loan_type", "mechanism_type", "scope_type"])

    write_rows(TABLES / "actor_third_party_dependence.csv", DEPENDENCE_FIELDS, dependence)
    write_rows(
        TABLES / "top_third_party_dependent_actors.csv",
        DEPENDENCE_FIELDS,
        [row for row in dependence if as_int(row["third_party_context_edge_degree"]) > 0][:40],
    )
    write_rows(TABLES / "direct_vs_third_party_graph_summary.csv", GRAPH_SUMMARY_FIELDS, graph_rows)
    write_rows(TABLES / "third_party_by_actor_type.csv", ACTOR_TYPE_FIELDS, actor_type_rows)
    write_rows(TABLES / "third_party_by_mechanism.csv", MECHANISM_FIELDS, mechanism_rows)
    write_rows(TABLES / "third_party_by_mechanism_and_scope.csv", MECHANISM_SCOPE_FIELDS, mechanism_scope_rows)
    write_findings(graph_rows)

    print(f"direct_edges={graph_rows[0]['edge_count']}")
    print(f"context_edges={graph_rows[1]['edge_count']}")
    print(f"actor_dependence_rows={len(dependence)}")
    print(f"mechanism_rows={len(mechanism_rows)}")


if __name__ == "__main__":
    main()
