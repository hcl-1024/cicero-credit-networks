#!/usr/bin/env python3
"""Analyze graph-ready Cicero loan edge data."""

from __future__ import annotations

import csv
import math
from html import escape
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "build" / "analysis"
CORE = ANALYSIS / "core"
NETWORK = ANALYSIS / "network"
EDGE_SOURCE = CORE / "cicero_loan_network_edges.csv"
LOAN_SOURCE = CORE / "cicero_loans_analysis_ready.csv"

NODE_FIELDS = [
    "canonical_party",
    "total_degree",
    "weighted_degree",
    "in_degree",
    "out_degree",
    "direct_financial_degree",
    "third_party_context_degree",
    "borrower_to_lender_out",
    "borrower_to_lender_in",
    "third_party_context_out",
    "third_party_context_in",
    "record_count",
    "episode_count",
    "confidence_values",
    "episode_groups",
]

WEIGHTED_EDGE_FIELDS = [
    "source_canonical",
    "target_canonical",
    "edge_type",
    "weight",
    "record_count",
    "records",
    "episode_count",
    "episode_groups",
    "confidence_values",
]

EDGE_TYPE_FIELDS = [
    "edge_type",
    "edge_count",
    "unique_source_count",
    "unique_target_count",
    "unique_party_count",
    "record_count",
    "episode_count",
]

EPISODE_FIELDS = [
    "episode_group",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "context_to_direct_ratio",
    "unique_party_count",
    "record_count",
    "density_undirected",
    "component_count",
    "obligation_types",
    "top_parties",
]

COMPONENT_FIELDS = [
    "component_id",
    "party_count",
    "edge_count",
    "direct_edge_count",
    "record_count",
    "parties",
    "episode_groups",
]

CENTRALITY_FIELDS = [
    "centrality_rank",
    "canonical_party",
    "total_degree_centrality",
    "in_degree_centrality",
    "out_degree_centrality",
    "direct_financial_degree_centrality",
    "third_party_context_degree_centrality",
    "closeness_centrality",
    "betweenness_centrality",
    "pagerank",
    "reachable_party_count",
    "component_size",
]

LAYER_FIELDS = [
    "layer",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "unique_party_count",
    "record_count",
    "component_count",
    "largest_component_party_count",
    "density_undirected",
    "top_weighted_degree_parties",
    "top_pagerank_parties",
    "top_betweenness_parties",
]

ROBUSTNESS_FIELDS = [
    "scenario",
    "layer",
    "removed_party",
    "edge_count",
    "unique_party_count",
    "record_count",
    "component_count",
    "largest_component_party_count",
    "density_undirected",
    "top_weighted_degree_parties",
    "top_pagerank_parties",
    "top_betweenness_parties",
]

OBLIGATION_TYPE_FIELDS = [
    "analysis_loan_type",
    "canonical_loan_type",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "unique_party_count",
    "record_count",
    "episode_count",
    "top_parties",
    "direct_role_details",
    "context_role_details",
]

DIRECT_ROLE_DETAIL_FIELDS = [
    "role_detail",
    "edge_count",
    "unique_source_count",
    "unique_target_count",
    "unique_party_count",
    "record_count",
    "episode_count",
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


def join_sorted(values: set[str]) -> str:
    return "; ".join(sorted(value for value in values if value))


def top_counts(counter: Counter[str], limit: int = 5) -> str:
    return "; ".join(f"{key} ({value})" for key, value in counter.most_common(limit))


def top_metric_values(rows: list[dict[str, object]], field: str, limit: int = 5) -> str:
    values = sorted(
        ((str(row["canonical_party"]), float(row[field])) for row in rows),
        key=lambda item: (-item[1], item[0]),
    )
    return "; ".join(f"{party} ({value:.6f})" for party, value in values[:limit])


def format_float(value: float) -> str:
    return f"{value:.6f}"


def edge_parties(edge: dict[str, str]) -> tuple[str, str]:
    return edge["source_canonical"].strip(), edge["target_canonical"].strip()


def is_direct_edge(edge: dict[str, str]) -> bool:
    return edge["edge_type"] == "borrower_to_lender"


def edge_nodes(edges: list[dict[str, str]]) -> set[str]:
    return {party for edge in edges for party in edge_parties(edge) if party}


def undirected_density(edges: list[dict[str, str]]) -> float:
    nodes = edge_nodes(edges)
    node_count = len(nodes)
    if node_count < 2:
        return 0.0
    pairs = {tuple(sorted(edge_parties(edge))) for edge in edges if all(edge_parties(edge))}
    return len(pairs) / (node_count * (node_count - 1) / 2)


def connected_components(edges: list[dict[str, str]]) -> list[set[str]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source, target = edge_parties(edge)
        if not source or not target:
            continue
        neighbors[source].add(target)
        neighbors[target].add(source)

    seen: set[str] = set()
    components: list[set[str]] = []
    for node in sorted(neighbors):
        if node in seen:
            continue
        component: set[str] = set()
        queue: deque[str] = deque([node])
        seen.add(node)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in sorted(neighbors[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return sorted(components, key=lambda item: (-len(item), sorted(item)))


def graph_indexes(
    edges: list[dict[str, str]]
) -> tuple[
    list[str],
    dict[str, set[str]],
    dict[str, dict[str, int]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    nodes: set[str] = set()
    undirected_neighbors: dict[str, set[str]] = defaultdict(set)
    weighted_out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    in_neighbors: dict[str, set[str]] = defaultdict(set)
    out_neighbors: dict[str, set[str]] = defaultdict(set)
    direct_neighbors: dict[str, set[str]] = defaultdict(set)
    third_party_neighbors: dict[str, set[str]] = defaultdict(set)

    for edge in edges:
        source, target = edge_parties(edge)
        if not source or not target:
            continue
        nodes.update([source, target])
        undirected_neighbors[source].add(target)
        undirected_neighbors[target].add(source)
        weighted_out[source][target] += 1
        out_neighbors[source].add(target)
        in_neighbors[target].add(source)
        if is_direct_edge(edge):
            direct_neighbors[source].add(target)
            direct_neighbors[target].add(source)
        else:
            third_party_neighbors[source].add(target)
            third_party_neighbors[target].add(source)

    ordered_nodes = sorted(nodes)
    for node in ordered_nodes:
        undirected_neighbors[node]
        weighted_out[node]
        in_neighbors[node]
        out_neighbors[node]
        direct_neighbors[node]
        third_party_neighbors[node]
    return (
        ordered_nodes,
        undirected_neighbors,
        weighted_out,
        in_neighbors,
        out_neighbors,
        direct_neighbors,
        third_party_neighbors,
    )


def shortest_path_lengths(start: str, neighbors: dict[str, set[str]]) -> dict[str, int]:
    distances = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in sorted(neighbors[current]):
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            queue.append(neighbor)
    return distances


def betweenness_scores(nodes: list[str], neighbors: dict[str, set[str]]) -> dict[str, float]:
    scores = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {node: [] for node in nodes}
        path_counts = dict.fromkeys(nodes, 0.0)
        path_counts[source] = 1.0
        distances = dict.fromkeys(nodes, -1)
        distances[source] = 0
        queue: deque[str] = deque([source])

        while queue:
            current = queue.popleft()
            stack.append(current)
            for neighbor in sorted(neighbors[current]):
                if distances[neighbor] < 0:
                    queue.append(neighbor)
                    distances[neighbor] = distances[current] + 1
                if distances[neighbor] == distances[current] + 1:
                    path_counts[neighbor] += path_counts[current]
                    predecessors[neighbor].append(current)

        dependencies = dict.fromkeys(nodes, 0.0)
        while stack:
            node = stack.pop()
            for predecessor in predecessors[node]:
                if path_counts[node]:
                    share = path_counts[predecessor] / path_counts[node]
                    dependencies[predecessor] += share * (1.0 + dependencies[node])
            if node != source:
                scores[node] += dependencies[node]

    if len(nodes) > 2:
        scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
        for node in nodes:
            scores[node] *= scale
    return scores


def pagerank_scores(
    nodes: list[str],
    weighted_out: dict[str, dict[str, int]],
    damping: float = 0.85,
    max_iterations: int = 100,
    tolerance: float = 1.0e-12,
) -> dict[str, float]:
    if not nodes:
        return {}
    node_count = len(nodes)
    ranks = dict.fromkeys(nodes, 1.0 / node_count)
    out_weight = {node: sum(weighted_out[node].values()) for node in nodes}

    for _ in range(max_iterations):
        dangling_rank = sum(ranks[node] for node in nodes if out_weight[node] == 0)
        next_ranks = dict.fromkeys(nodes, (1.0 - damping) / node_count + damping * dangling_rank / node_count)
        for source in nodes:
            if out_weight[source] == 0:
                continue
            for target, weight in weighted_out[source].items():
                next_ranks[target] += damping * ranks[source] * weight / out_weight[source]
        delta = sum(abs(next_ranks[node] - ranks[node]) for node in nodes)
        ranks = next_ranks
        if delta < tolerance:
            break
    return ranks


def build_centrality_metrics(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    (
        nodes,
        undirected_neighbors,
        weighted_out,
        in_neighbors,
        out_neighbors,
        direct_neighbors,
        third_party_neighbors,
    ) = graph_indexes(edges)
    node_count = len(nodes)
    denominator = node_count - 1 if node_count > 1 else 1
    betweenness = betweenness_scores(nodes, undirected_neighbors)
    pagerank = pagerank_scores(nodes, weighted_out)

    rows = []
    for node in nodes:
        distances = shortest_path_lengths(node, undirected_neighbors)
        reachable_count = len(distances) - 1
        distance_sum = sum(distance for party, distance in distances.items() if party != node)
        closeness = 0.0
        if distance_sum and denominator:
            closeness = (reachable_count / distance_sum) * (reachable_count / denominator)
        rows.append(
            {
                "canonical_party": node,
                "total_degree_centrality": len(in_neighbors[node] | out_neighbors[node]) / denominator,
                "in_degree_centrality": len(in_neighbors[node]) / denominator,
                "out_degree_centrality": len(out_neighbors[node]) / denominator,
                "direct_financial_degree_centrality": len(direct_neighbors[node]) / denominator,
                "third_party_context_degree_centrality": len(third_party_neighbors[node]) / denominator,
                "closeness_centrality": closeness,
                "betweenness_centrality": betweenness[node],
                "pagerank": pagerank[node],
                "reachable_party_count": reachable_count,
                "component_size": len(distances),
            }
        )

    rows = sorted(
        rows,
        key=lambda row: (
            -float(row["pagerank"]),
            -float(row["betweenness_centrality"]),
            -float(row["closeness_centrality"]),
            row["canonical_party"],
        ),
    )
    for index, row in enumerate(rows, start=1):
        row["centrality_rank"] = index
        for field in [
            "total_degree_centrality",
            "in_degree_centrality",
            "out_degree_centrality",
            "direct_financial_degree_centrality",
            "third_party_context_degree_centrality",
            "closeness_centrality",
            "betweenness_centrality",
            "pagerank",
        ]:
            row[field] = f"{float(row[field]):.6f}"
    return rows


def build_node_metrics(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "in_neighbors": set(),
            "out_neighbors": set(),
            "direct_neighbors": set(),
            "third_party_neighbors": set(),
            "weighted_degree": 0,
            "borrower_to_lender_out": 0,
            "borrower_to_lender_in": 0,
            "third_party_context_out": 0,
            "third_party_context_in": 0,
            "records": set(),
            "episodes": set(),
            "confidences": set(),
        }
    )

    for edge in edges:
        source, target = edge_parties(edge)
        if not source or not target:
            continue
        edge_type = edge["edge_type"]
        for party in [source, target]:
            stats[party]["weighted_degree"] = int(stats[party]["weighted_degree"]) + 1
            stats[party]["records"].add(edge["record_id"])
            stats[party]["episodes"].add(edge["episode_group"])
            stats[party]["confidences"].add(edge["confidence"])
        stats[source]["out_neighbors"].add(target)
        stats[target]["in_neighbors"].add(source)
        if edge_type == "borrower_to_lender":
            stats[source]["borrower_to_lender_out"] = int(stats[source]["borrower_to_lender_out"]) + 1
            stats[target]["borrower_to_lender_in"] = int(stats[target]["borrower_to_lender_in"]) + 1
            stats[source]["direct_neighbors"].add(target)
            stats[target]["direct_neighbors"].add(source)
        else:
            stats[source]["third_party_context_out"] = int(stats[source]["third_party_context_out"]) + 1
            stats[target]["third_party_context_in"] = int(stats[target]["third_party_context_in"]) + 1
            stats[source]["third_party_neighbors"].add(target)
            stats[target]["third_party_neighbors"].add(source)

    rows = []
    for party, values in stats.items():
        in_neighbors = values["in_neighbors"]
        out_neighbors = values["out_neighbors"]
        direct_neighbors = values["direct_neighbors"]
        third_party_neighbors = values["third_party_neighbors"]
        rows.append(
            {
                "canonical_party": party,
                "total_degree": len(in_neighbors | out_neighbors),
                "weighted_degree": values["weighted_degree"],
                "in_degree": len(in_neighbors),
                "out_degree": len(out_neighbors),
                "direct_financial_degree": len(direct_neighbors),
                "third_party_context_degree": len(third_party_neighbors),
                "borrower_to_lender_out": values["borrower_to_lender_out"],
                "borrower_to_lender_in": values["borrower_to_lender_in"],
                "third_party_context_out": values["third_party_context_out"],
                "third_party_context_in": values["third_party_context_in"],
                "record_count": len(values["records"]),
                "episode_count": len(values["episodes"]),
                "confidence_values": join_sorted(values["confidences"]),
                "episode_groups": join_sorted(values["episodes"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["weighted_degree"]), row["canonical_party"]))


def build_weighted_edges(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {"weight": 0, "records": set(), "episodes": set(), "confidences": set()}
    )
    for edge in edges:
        source, target = edge_parties(edge)
        if not source or not target:
            continue
        key = (source, target, edge["edge_type"])
        grouped[key]["weight"] = int(grouped[key]["weight"]) + 1
        grouped[key]["records"].add(edge["record_id"])
        grouped[key]["episodes"].add(edge["episode_group"])
        grouped[key]["confidences"].add(edge["confidence"])

    rows = []
    for (source, target, edge_type), values in grouped.items():
        rows.append(
            {
                "source_canonical": source,
                "target_canonical": target,
                "edge_type": edge_type,
                "weight": values["weight"],
                "record_count": len(values["records"]),
                "records": join_sorted(values["records"]),
                "episode_count": len(values["episodes"]),
                "episode_groups": join_sorted(values["episodes"]),
                "confidence_values": join_sorted(values["confidences"]),
            }
        )
    return sorted(
        rows,
        key=lambda row: (-int(row["weight"]), row["source_canonical"], row["target_canonical"], row["edge_type"]),
    )


def build_edge_type_summary(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"count": 0, "sources": set(), "targets": set(), "records": set(), "episodes": set()}
    )
    for edge in edges:
        source, target = edge_parties(edge)
        edge_type = edge["edge_type"]
        grouped[edge_type]["count"] = int(grouped[edge_type]["count"]) + 1
        grouped[edge_type]["sources"].add(source)
        grouped[edge_type]["targets"].add(target)
        grouped[edge_type]["records"].add(edge["record_id"])
        grouped[edge_type]["episodes"].add(edge["episode_group"])

    rows = []
    for edge_type, values in grouped.items():
        parties = values["sources"] | values["targets"]
        rows.append(
            {
                "edge_type": edge_type,
                "edge_count": values["count"],
                "unique_source_count": len(values["sources"]),
                "unique_target_count": len(values["targets"]),
                "unique_party_count": len(parties),
                "record_count": len(values["records"]),
                "episode_count": len(values["episodes"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["edge_type"]))


def build_episode_summary(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "edge_count": 0,
            "direct_edge_count": 0,
            "third_party_context_edge_count": 0,
            "parties": set(),
            "records": set(),
            "party_counts": Counter(),
            "obligation_types": Counter(),
            "edges": [],
        }
    )
    for edge in edges:
        source, target = edge_parties(edge)
        episode = edge["episode_group"] or "(blank)"
        grouped[episode]["edge_count"] = int(grouped[episode]["edge_count"]) + 1
        if is_direct_edge(edge):
            grouped[episode]["direct_edge_count"] = int(grouped[episode]["direct_edge_count"]) + 1
        else:
            grouped[episode]["third_party_context_edge_count"] = int(grouped[episode]["third_party_context_edge_count"]) + 1
        grouped[episode]["parties"].update([source, target])
        grouped[episode]["records"].add(edge["record_id"])
        grouped[episode]["party_counts"].update([source, target])
        if is_direct_edge(edge):
            grouped[episode]["obligation_types"].update([edge["role_detail"]])
        grouped[episode]["edges"].append(edge)

    rows = []
    for episode, values in grouped.items():
        direct_count = int(values["direct_edge_count"])
        context_count = int(values["third_party_context_edge_count"])
        ratio = context_count / direct_count if direct_count else 0.0
        rows.append(
            {
                "episode_group": episode,
                "edge_count": values["edge_count"],
                "direct_edge_count": direct_count,
                "third_party_context_edge_count": context_count,
                "context_to_direct_ratio": format_float(ratio),
                "unique_party_count": len(values["parties"]),
                "record_count": len(values["records"]),
                "density_undirected": format_float(undirected_density(values["edges"])),
                "component_count": len(connected_components(values["edges"])),
                "obligation_types": top_counts(values["obligation_types"]),
                "top_parties": top_counts(values["party_counts"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["episode_group"]))


def build_component_summary(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    components = connected_components(edges)
    rows = []
    for index, component in enumerate(components, start=1):
        component_edges = [
            edge
            for edge in edges
            if edge["source_canonical"] in component and edge["target_canonical"] in component
        ]
        rows.append(
            {
                "component_id": index,
                "party_count": len(component),
                "edge_count": len(component_edges),
                "direct_edge_count": sum(1 for edge in component_edges if is_direct_edge(edge)),
                "record_count": len({edge["record_id"] for edge in component_edges}),
                "parties": join_sorted(component),
                "episode_groups": join_sorted({edge["episode_group"] for edge in component_edges}),
            }
        )
    return rows


def summarize_graph_layer(layer: str, edges: list[dict[str, str]]) -> dict[str, object]:
    node_rows = build_node_metrics(edges)
    centrality_rows = build_centrality_metrics(edges)
    components = connected_components(edges)
    direct_count = sum(1 for edge in edges if is_direct_edge(edge))
    context_count = len(edges) - direct_count

    return {
        "layer": layer,
        "edge_count": len(edges),
        "direct_edge_count": direct_count,
        "third_party_context_edge_count": context_count,
        "unique_party_count": len(edge_nodes(edges)),
        "record_count": len({edge["record_id"] for edge in edges}),
        "component_count": len(components),
        "largest_component_party_count": max((len(component) for component in components), default=0),
        "density_undirected": format_float(undirected_density(edges)),
        "top_weighted_degree_parties": top_counts(
            Counter({str(row["canonical_party"]): int(row["weighted_degree"]) for row in node_rows})
        ),
        "top_pagerank_parties": top_metric_values(centrality_rows, "pagerank"),
        "top_betweenness_parties": top_metric_values(centrality_rows, "betweenness_centrality"),
    }


def build_layer_comparison(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        summarize_graph_layer("combined", edges),
        summarize_graph_layer("direct_borrower_lender", [edge for edge in edges if is_direct_edge(edge)]),
        summarize_graph_layer("third_party_context", [edge for edge in edges if not is_direct_edge(edge)]),
    ]


def build_cicero_removed_robustness(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    layer_sets = [
        ("combined", edges),
        ("direct_borrower_lender", [edge for edge in edges if is_direct_edge(edge)]),
        ("third_party_context", [edge for edge in edges if not is_direct_edge(edge)]),
    ]
    for layer, layer_edges in layer_sets:
        for scenario, scenario_edges in [
            ("baseline", layer_edges),
            ("without_cicero", [
                edge for edge in layer_edges if "Cicero" not in set(edge_parties(edge))
            ]),
        ]:
            row = summarize_graph_layer(layer, scenario_edges)
            row["scenario"] = scenario
            row["removed_party"] = "Cicero" if scenario == "without_cicero" else ""
            rows.append(row)
    return rows


def build_record_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["record_id"]: row for row in load_rows(path)}


def build_obligation_type_summary(
    edges: list[dict[str, str]],
    record_lookup: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "edges": [],
            "parties": set(),
            "records": set(),
            "episodes": set(),
            "party_counts": Counter(),
            "direct_role_details": Counter(),
            "context_role_details": Counter(),
        }
    )
    for edge in edges:
        record = record_lookup.get(edge["record_id"], {})
        analysis_type = record.get("analysis_loan_type") or edge["role_detail"] or "(blank)"
        canonical_type = record.get("loan_type") or ""
        key = (analysis_type, canonical_type)
        source, target = edge_parties(edge)
        grouped[key]["edges"].append(edge)
        grouped[key]["parties"].update([source, target])
        grouped[key]["records"].add(edge["record_id"])
        grouped[key]["episodes"].add(edge["episode_group"])
        grouped[key]["party_counts"].update([source, target])
        if is_direct_edge(edge):
            grouped[key]["direct_role_details"].update([edge["role_detail"]])
        else:
            grouped[key]["context_role_details"].update([edge["role_detail"]])

    rows = []
    for (analysis_type, canonical_type), values in grouped.items():
        type_edges = values["edges"]
        rows.append(
            {
                "analysis_loan_type": analysis_type,
                "canonical_loan_type": canonical_type,
                "edge_count": len(type_edges),
                "direct_edge_count": sum(1 for edge in type_edges if is_direct_edge(edge)),
                "third_party_context_edge_count": sum(1 for edge in type_edges if not is_direct_edge(edge)),
                "unique_party_count": len(values["parties"]),
                "record_count": len(values["records"]),
                "episode_count": len(values["episodes"]),
                "top_parties": top_counts(values["party_counts"]),
                "direct_role_details": top_counts(values["direct_role_details"]),
                "context_role_details": top_counts(values["context_role_details"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["analysis_loan_type"]))


def build_direct_role_detail_summary(edges: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"count": 0, "sources": set(), "targets": set(), "records": set(), "episodes": set()}
    )
    for edge in edges:
        if not is_direct_edge(edge):
            continue
        source, target = edge_parties(edge)
        role_detail = edge["role_detail"] or "(blank)"
        grouped[role_detail]["count"] = int(grouped[role_detail]["count"]) + 1
        grouped[role_detail]["sources"].add(source)
        grouped[role_detail]["targets"].add(target)
        grouped[role_detail]["records"].add(edge["record_id"])
        grouped[role_detail]["episodes"].add(edge["episode_group"])

    rows = []
    for role_detail, values in grouped.items():
        parties = values["sources"] | values["targets"]
        rows.append(
            {
                "role_detail": role_detail,
                "edge_count": values["count"],
                "unique_source_count": len(values["sources"]),
                "unique_target_count": len(values["targets"]),
                "unique_party_count": len(parties),
                "record_count": len(values["records"]),
                "episode_count": len(values["episodes"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["role_detail"]))


def write_markdown_summary(
    edges: list[dict[str, str]],
    node_rows: list[dict[str, object]],
    weighted_edge_rows: list[dict[str, object]],
    centrality_rows: list[dict[str, object]],
    component_rows: list[dict[str, object]],
    layer_rows: list[dict[str, object]],
    robustness_rows: list[dict[str, object]],
    obligation_type_rows: list[dict[str, object]],
    direct_role_detail_rows: list[dict[str, object]],
) -> None:
    direct_edges = [edge for edge in edges if is_direct_edge(edge)]
    third_party_edges = [edge for edge in edges if not is_direct_edge(edge)]
    unique_parties = {party for edge in edges for party in edge_parties(edge) if party}
    records = {edge["record_id"] for edge in edges}
    episodes = {edge["episode_group"] for edge in edges if edge["episode_group"]}

    lines = [
        "# Cicero Loan Edge Analysis",
        "",
        "Generated from `analysis/core/cicero_loan_network_edges.csv` via `scripts/analysis/analyze_loan_edges.py`.",
        "",
        "## Graph Shape",
        "",
        f"- Edge rows: {len(edges)}.",
        f"- Unique canonical parties: {len(unique_parties)}.",
        f"- Source records represented: {len(records)}.",
        f"- Episode groups represented: {len(episodes)}.",
        f"- Direct borrower-to-lender edges: {len(direct_edges)}.",
        f"- Third-party context edges: {len(third_party_edges)}.",
        f"- Connected components, treating edges as undirected for component detection: {len(component_rows)}.",
        "",
        "## Top Parties By Weighted Degree",
        "",
    ]
    for row in node_rows[:10]:
        lines.append(
            f"- {row['canonical_party']}: weighted degree {row['weighted_degree']}, "
            f"direct degree {row['direct_financial_degree']}, "
            f"third-party context degree {row['third_party_context_degree']}."
        )

    lines.extend(["", "## Top Parties By Centrality", ""])
    for row in centrality_rows[:10]:
        lines.append(
            f"- {row['canonical_party']}: PageRank {row['pagerank']}, "
            f"betweenness {row['betweenness_centrality']}, "
            f"closeness {row['closeness_centrality']}."
        )

    lines.extend(["", "## Top Repeated Canonical Edges", ""])
    for row in weighted_edge_rows[:10]:
        lines.append(
            f"- {row['source_canonical']} -> {row['target_canonical']} "
            f"({row['edge_type']}): weight {row['weight']}, records {row['record_count']}."
        )

    lines.extend(["", "## Three-Layer Graph Reading", ""])
    for row in layer_rows:
        lines.append(
            f"- {row['layer']}: {row['edge_count']} edges, {row['unique_party_count']} parties, "
            f"{row['component_count']} component(s), largest component {row['largest_component_party_count']} parties, "
            f"undirected density {row['density_undirected']}."
        )

    lines.extend(["", "## Cicero-Removed Robustness", ""])
    without_cicero = [row for row in robustness_rows if row["scenario"] == "without_cicero"]
    for row in without_cicero:
        lines.append(
            f"- {row['layer']}: after removing Cicero, {row['edge_count']} edges and "
            f"{row['component_count']} component(s) remain; largest component has "
            f"{row['largest_component_party_count']} parties; top weighted-degree parties: "
            f"{row['top_weighted_degree_parties'] or 'none'}."
        )

    lines.extend(["", "## Obligation Types In The Edge Network", ""])
    for row in obligation_type_rows:
        type_label = str(row["analysis_loan_type"])
        if row["canonical_loan_type"] and row["canonical_loan_type"] != row["analysis_loan_type"]:
            type_label = f"{type_label} under canonical {row['canonical_loan_type']}"
        lines.append(
            f"- {type_label}: {row['edge_count']} edge rows "
            f"({row['direct_edge_count']} direct, {row['third_party_context_edge_count']} context), "
            f"{row['record_count']} records, top parties: {row['top_parties']}."
        )

    lines.extend(["", "## Direct Edge Role Details", ""])
    for row in direct_role_detail_rows:
        lines.append(
            f"- {row['role_detail']}: {row['edge_count']} direct edge rows, "
            f"{row['record_count']} records, {row['unique_party_count']} parties."
        )

    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- Use `borrower_to_lender` edges for direct financial relationships.",
            "- Use third-party context edges to study agents, managers, sureties, family actors, and account handlers.",
            "- Read the combined, direct-only, and context-only layers side by side: the combined graph shows documentary entanglement, the direct layer shows explicit financial counterparties, and the context layer shows social/administrative machinery.",
            "- Removing Cicero is a robustness check for epistolary vantage-point bias; it should not be read as removing Cicero from the historical situation.",
            "- Loan-type summaries inherit `analysis_loan_type` and canonical `loan_type` from the record-level analysis table, because context edges do not themselves encode a separate obligation type.",
            "- Alternative mathematical treatments for loan type include separate type-specific layers, type-weighted adjacency matrices, bipartite record-party graphs with loan type as a record attribute, and multilevel models where edge type, loan type, confidence, episode, and year are separate covariates.",
            "- Placeholder, role-only, and non-actor context labels are archived as provenance but excluded from final canonical graph nodes and centrality metrics.",
            "- Weighted degree counts repeated attestations and context links, not money volume.",
            "- A dependency-free SVG visualization is generated at `analysis/network/cicero_loan_network.svg`; red edges are direct borrower-to-lender links and gray-blue edges are third-party context links.",
            "- Centrality values are structural measures over canonical party links; PageRank uses directed weighted edges, while closeness and betweenness use the undirected graph.",
            "- Do not infer aggregate amounts from this graph while amount normalization remains incomplete.",
            "",
        ]
    )

    NETWORK.mkdir(parents=True, exist_ok=True)
    (NETWORK / "network_analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_network_svg(
    edges: list[dict[str, str]],
    node_rows: list[dict[str, object]],
    weighted_edge_rows: list[dict[str, object]],
    component_rows: list[dict[str, object]],
) -> str:
    node_weights = {str(row["canonical_party"]): int(row["weighted_degree"]) for row in node_rows}
    node_direct = {str(row["canonical_party"]): int(row["direct_financial_degree"]) for row in node_rows}
    components = []
    for component in component_rows:
        parties = [party.strip() for party in str(component["parties"]).split(";") if party.strip()]
        if parties:
            components.append(parties)
    if not components:
        components = [sorted(node_weights)]

    positions: dict[str, tuple[float, float]] = {}
    centers = [(565, 465, 330), (1045, 235, 130), (1025, 680, 115), (235, 175, 100)]
    for component_index, parties in enumerate(components):
        parties = sorted(parties, key=lambda party: (-node_weights.get(party, 0), party))
        center_x, center_y, radius = centers[min(component_index, len(centers) - 1)]
        if len(parties) == 1:
            positions[parties[0]] = (center_x, center_y)
            continue
        for index, party in enumerate(parties):
            angle = -math.pi / 2 + 2 * math.pi * index / len(parties)
            # Slightly pull very central nodes toward the middle for legibility.
            node_radius = radius * (0.45 if index == 0 and len(parties) > 8 else 1.0)
            positions[party] = (
                center_x + node_radius * math.cos(angle),
                center_y + node_radius * math.sin(angle),
            )

    edge_lines = []
    sorted_edges = sorted(
        weighted_edge_rows,
        key=lambda row: (0 if row["edge_type"] != "borrower_to_lender" else 1, int(row["weight"])),
    )
    for row in sorted_edges:
        source = str(row["source_canonical"])
        target = str(row["target_canonical"])
        if source not in positions or target not in positions:
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        direct = row["edge_type"] == "borrower_to_lender"
        color = "#b44b3f" if direct else "#7f92a5"
        opacity = "0.82" if direct else "0.34"
        width_value = 1.0 + math.sqrt(int(row["weight"])) * (1.15 if direct else 0.75)
        edge_lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width_value:.2f}" stroke-opacity="{opacity}" '
            f'marker-end="url(#arrow-{"direct" if direct else "context"})">'
            f"<title>{escape(source)} -> {escape(target)}; {escape(str(row['edge_type']))}; "
            f"weight {escape(str(row['weight']))}; records {escape(str(row['records']))}</title></line>"
        )

    node_groups = []
    for party, (x, y) in sorted(positions.items(), key=lambda item: (-node_weights.get(item[0], 0), item[0])):
        weight = node_weights.get(party, 1)
        direct_degree = node_direct.get(party, 0)
        radius = 5.5 + min(18.0, math.sqrt(weight) * 2.4)
        fill = "#2f6f73" if direct_degree else "#6d7890"
        if party == "Cicero":
            fill = "#1e4f57"
        elif party in {"Atticus", "Tiro", "Terentia", "Philotimus"}:
            fill = "#6f5f96"
        label_anchor = "middle"
        label_y = y - radius - 5
        node_groups.append(
            f'<g class="node"><circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" '
            f'stroke="#ffffff" stroke-width="1.8"><title>{escape(party)}; weighted degree {weight}; '
            f'direct financial degree {direct_degree}</title></circle>'
            f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="{label_anchor}">{escape(party)}</text></g>'
        )

    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="920" viewBox="0 0 1280 920" role="img" aria-labelledby="title desc">',
            "<title id=\"title\">Cicero Loan Network</title>",
            "<desc id=\"desc\">Graph of direct borrower-lender edges and third-party context edges in the Cicero loan extraction dataset.</desc>",
            "<defs>",
            '<marker id="arrow-direct" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><polygon points="0 0, 8 3.5, 0 7" fill="#b44b3f"/></marker>',
            '<marker id="arrow-context" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><polygon points="0 0, 7 3.5, 0 7" fill="#7f92a5"/></marker>',
            "<style>",
            "svg { background: #fbfaf7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }",
            ".title { font-size: 24px; font-weight: 650; fill: #223033; }",
            ".subtitle, .legend { font-size: 13px; fill: #526066; }",
            ".node text { font-size: 10.5px; fill: #243136; paint-order: stroke; stroke: #fbfaf7; stroke-width: 3px; stroke-linejoin: round; }",
            "</style>",
            "</defs>",
            '<text class="title" x="32" y="42">Cicero Loan Network</text>',
            '<text class="subtitle" x="32" y="66">Direct borrower-to-lender edges are red; third-party managerial, surety, household, and accounting context edges are gray-blue. Node size follows weighted degree, not money volume.</text>',
            '<line x1="34" y1="96" x2="108" y2="96" stroke="#b44b3f" stroke-width="3" marker-end="url(#arrow-direct)"/>',
            '<text class="legend" x="122" y="100">direct borrower-to-lender</text>',
            '<line x1="315" y1="96" x2="389" y2="96" stroke="#7f92a5" stroke-width="3" stroke-opacity="0.6" marker-end="url(#arrow-context)"/>',
            '<text class="legend" x="403" y="100">third-party context</text>',
            *edge_lines,
            *node_groups,
            "</svg>",
        ]
    )


def main() -> None:
    edges = load_rows(EDGE_SOURCE)
    record_lookup = build_record_lookup(LOAN_SOURCE)
    node_rows = build_node_metrics(edges)
    weighted_edge_rows = build_weighted_edges(edges)
    edge_type_rows = build_edge_type_summary(edges)
    episode_rows = build_episode_summary(edges)
    component_rows = build_component_summary(edges)
    centrality_rows = build_centrality_metrics(edges)
    layer_rows = build_layer_comparison(edges)
    robustness_rows = build_cicero_removed_robustness(edges)
    obligation_type_rows = build_obligation_type_summary(edges, record_lookup)
    direct_role_detail_rows = build_direct_role_detail_summary(edges)

    write_rows(NETWORK / "network_node_metrics.csv", NODE_FIELDS, node_rows)
    write_rows(NETWORK / "network_edge_weights.csv", WEIGHTED_EDGE_FIELDS, weighted_edge_rows)
    write_rows(NETWORK / "network_edge_type_summary.csv", EDGE_TYPE_FIELDS, edge_type_rows)
    write_rows(NETWORK / "network_episode_summary.csv", EPISODE_FIELDS, episode_rows)
    write_rows(NETWORK / "network_component_summary.csv", COMPONENT_FIELDS, component_rows)
    write_rows(NETWORK / "network_centrality_metrics.csv", CENTRALITY_FIELDS, centrality_rows)
    write_rows(NETWORK / "network_layer_comparison.csv", LAYER_FIELDS, layer_rows)
    write_rows(NETWORK / "network_cicero_removed_robustness.csv", ROBUSTNESS_FIELDS, robustness_rows)
    write_rows(NETWORK / "network_obligation_type_summary.csv", OBLIGATION_TYPE_FIELDS, obligation_type_rows)
    write_rows(NETWORK / "network_direct_role_detail_summary.csv", DIRECT_ROLE_DETAIL_FIELDS, direct_role_detail_rows)
    write_markdown_summary(
        edges,
        node_rows,
        weighted_edge_rows,
        centrality_rows,
        component_rows,
        layer_rows,
        robustness_rows,
        obligation_type_rows,
        direct_role_detail_rows,
    )
    (NETWORK / "cicero_loan_network.svg").write_text(
        build_network_svg(edges, node_rows, weighted_edge_rows, component_rows),
        encoding="utf-8",
    )

    print(f"edge_rows={len(edges)}")
    print(f"node_metric_rows={len(node_rows)}")
    print(f"weighted_edge_rows={len(weighted_edge_rows)}")
    print(f"component_rows={len(component_rows)}")
    print(f"centrality_metric_rows={len(centrality_rows)}")
    print(f"layer_rows={len(layer_rows)}")
    print(f"robustness_rows={len(robustness_rows)}")
    print(f"obligation_type_rows={len(obligation_type_rows)}")
    if centrality_rows:
        top = centrality_rows[0]
        print(
            "top_centrality="
            f"{top['canonical_party']} "
            f"pagerank={top['pagerank']} "
            f"betweenness={top['betweenness_centrality']} "
            f"closeness={top['closeness_centrality']}"
        )


if __name__ == "__main__":
    main()
