#!/usr/bin/env python3
"""Build Objective 04 liquidity-stress and refinancing-pressure metrics."""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "canonical" / "cicero_credit_records.csv"
GRAPH_TABLES = ROOT / "build" / "analysis" / "graphs" / "tables"
BIPARTITE = GRAPH_TABLES / "record_party_bipartite.csv"
EDGES = GRAPH_TABLES / "actor_edges.csv"
EPISODES = GRAPH_TABLES / "episode_nodes.csv"
AMOUNTS = ROOT / "data" / "amounts" / "amount_values.csv"
OBJ_ROOT = ROOT / "results" / "official" / "objectives" / "04_credit_mechanisms"
TABLES = OBJ_ROOT / "tables"
GRAPH_VARIANTS = TABLES / "graph_variants"


RECORD_FIELDS = [
    "record_id",
    "source_letter_id",
    "episode_group",
    "year_bce",
    "confidence",
    "scope_type",
    "source_support_tier",
    "date_period",
    "mechanism_type",
    "analysis_loan_type",
    "status",
    "stress_flag",
    "stress_intensity_score",
    "stress_intensity_class",
    "refinancing_flag",
    "repayment_pressure_flag",
    "account_liquidity_flag",
    "surety_pressure_flag",
    "third_party_dependency_flag",
    "normalized_amount_flag",
    "strict_slice_flag",
    "latin_evidence",
    "english_evidence",
    "interpretive_note",
    "stress_evidence_terms",
    "stress_rationale",
]

ACTOR_ROLE_FIELDS = [
    "canonical_name",
    "node_id",
    "high_stress_record_count",
    "all_stress_record_count",
    "average_stress_score",
    "max_stress_score",
    "refinancing_record_count",
    "repayment_pressure_record_count",
    "strict_slice_high_stress_count",
    "role_mix",
    "mechanism_mix",
    "stress_context_edge_count",
    "third_party_dependency_record_count",
    "supporting_records",
]

EPISODE_FIELDS = [
    "episode_group",
    "stress_record_count",
    "high_stress_record_count",
    "average_stress_score",
    "max_stress_score",
    "dominant_stress_mechanism",
    "top_stressed_borrowers",
    "top_creditors_or_pressure_sources",
    "top_intermediaries",
    "normalized_amount_count",
    "strict_hs_total",
    "candidate_hs_total",
    "supporting_records",
]

YEAR_FIELDS = [
    "year_bce",
    "canonical_record_count",
    "stress_record_count",
    "high_stress_record_count",
    "strict_stress_record_count",
    "refinancing_record_count",
    "repayment_pressure_record_count",
    "normalized_amount_count",
    "strict_hs_total",
    "candidate_hs_total",
    "supporting_records",
]

SCOPE_FIELDS = [
    "slice_name",
    "record_count",
    "stress_record_count",
    "high_stress_record_count",
    "refinancing_record_count",
    "repayment_pressure_record_count",
    "strict_hs_total",
    "candidate_hs_total",
    "slice_rule",
]

AMOUNT_FIELDS = [
    "record_id",
    "amount_instance_id",
    "source_letter_id",
    "episode_group",
    "borrower",
    "lender",
    "mechanism_type",
    "stress_intensity_score",
    "stress_intensity_class",
    "amount_role",
    "amount_original",
    "normalized_amount_hs",
    "include_in_scale_strict",
    "include_in_scale_candidate",
    "normalization_certainty",
    "exclusion_reason",
]

CENTRALITY_FIELDS = [
    "variant_name",
    "centrality_rank",
    "node_id",
    "canonical_name",
    "weighted_degree",
    "direct_edge_degree",
    "context_edge_degree",
    "component_size",
    "pagerank",
    "betweenness",
]

DELTA_FIELDS = [
    "variant_name",
    "node_id",
    "canonical_name",
    "full_graph_rank",
    "stress_graph_rank",
    "rank_delta",
    "full_weighted_degree",
    "stress_weighted_degree",
    "degree_delta",
    "full_betweenness",
    "stress_betweenness",
    "betweenness_delta",
]

CHAIN_FIELDS = [
    "chain_id",
    "episode_group",
    "date_window",
    "supporting_record_ids",
    "supporting_letters",
    "primary_stressed_actors",
    "creditors_or_pressure_sources",
    "intermediaries",
    "fallback_types",
    "versura_flag",
    "failed_or_uncertain_source_flag",
    "sale_fallback_flag",
    "account_transfer_flag",
    "surety_flag",
    "repayment_pressure_flag",
    "third_party_dependency_flag",
    "record_count",
    "high_stress_record_count",
    "normalized_amount_count",
    "strict_hs_total",
    "candidate_hs_total",
    "chain_intensity_score",
    "chain_class",
    "latin_anchors",
    "interpretive_note",
    "confidence",
    "followup_needed",
]

CHAIN_RECORD_FIELDS = [
    "chain_id",
    "record_id",
    "source_letter_id",
    "episode_group",
    "year_bce",
    "borrower_or_stressed_actor",
    "creditor_or_pressure_source",
    "intermediaries",
    "mechanism_type",
    "stress_intensity_score",
    "stress_intensity_class",
    "fallback_types",
    "status",
    "latin_evidence",
    "stress_rationale",
]

EVIDENCE_FIELDS = [
    "claim_id",
    "claim_text",
    "supporting_record_ids",
    "supporting_outputs",
    "episode_id",
    "mechanism",
    "confidence",
    "caveat",
    "followup_needed",
]


REFI_TERMS = ["refinancing/versura", "versura", "refinanc"]
REPAYMENT_TERMS = [
    "repayment pressure",
    "overdue",
    "disputed",
    "non reddit",
    "sine mora",
    "coactus",
    "expressit",
    "urgent",
]
SUPPORT_TERMS = [
    "account/nomina",
    "nomen",
    "nomina",
    "rescribere",
    "permutatio",
    "satisdare",
    "satisdation",
    "sponsor",
    "surety",
    "guarantee",
]
SALE_TERMS = ["venditione", "vendam", "vender", "sale", "selling", "sell"]
FAILED_SOURCE_TERMS = ["non respond", "non reddit", "non potest", "nihil", "exigere", "expressit", "coactus", "cogor"]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def canonical_id(row: dict[str, str]) -> str:
    return (
        row.get("record_id")
        or row.get("merged_record_id")
        or row.get("canonical_record_id")
        or row.get("representative_record_id")
        or ""
    )


def split_values(value: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"[;,|]", value or "") if piece.strip()]


def join_sorted(values: set[str] | list[str]) -> str:
    return "; ".join(sorted({value for value in values if value}))


def top_counts(counter: Counter[str], limit: int = 5) -> str:
    return "; ".join(f"{key} ({value})" for key, value in counter.most_common(limit) if key)


def as_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def as_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def amount_sum(rows: list[dict[str, str]], include_field: str) -> int:
    return sum(as_int(row.get("normalized_amount_hs")) for row in rows if row.get(include_field) == "yes")


def first_nonblank(values: list[str], default: str = "") -> str:
    for value in values:
        if value:
            return value
    return default


def compact_text(value: str, limit: int = 140) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def actor_names_for_records(bip_rows: list[dict[str, str]], records: set[str], role: str, limit: int = 8) -> str:
    counts = Counter()
    for row in bip_rows:
        if row.get("record_id") not in records:
            continue
        if role == "intermediary":
            if row.get("is_third_party") == "yes":
                counts[row.get("canonical_name", "")] += 1
        elif row.get("role_type") == role:
            counts[row.get("canonical_name", "")] += 1
    return top_counts(counts, limit)


def actor_names_for_record(bip_rows: list[dict[str, str]], record_id: str, role: str, limit: int = 5) -> str:
    return actor_names_for_records(bip_rows, {record_id}, role, limit)


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def stress_class(score: int) -> str:
    if score == 0:
        return "no_stress_signal"
    if score == 1:
        return "indirect_liquidity_management"
    if score <= 3:
        return "moderate_pressure"
    return "high_refinancing_or_repayment_pressure"


def record_metadata(
    canonical_row: dict[str, str],
    bip_rows: list[dict[str, str]],
    amount_rows: list[dict[str, str]],
    edge_rows: list[dict[str, str]],
) -> dict[str, str]:
    text = " ".join(
        [
            canonical_row.get("loan_type", ""),
            canonical_row.get("status", ""),
            canonical_row.get("interest_or_terms", ""),
            canonical_row.get("latin_evidence", ""),
            canonical_row.get("english_evidence", ""),
            canonical_row.get("interpretive_note", ""),
            canonical_row.get("brief_description", ""),
            canonical_row.get("amount_note", ""),
        ]
    ).lower()

    mechanisms = Counter(row.get("mechanism_type", "") for row in bip_rows if row.get("mechanism_type"))
    mechanism = mechanisms.most_common(1)[0][0] if mechanisms else canonical_row.get("loan_type", "")
    loan_types = Counter(row.get("analysis_loan_type", "") for row in bip_rows if row.get("analysis_loan_type"))
    analysis_loan_type = loan_types.most_common(1)[0][0] if loan_types else canonical_row.get("loan_type", "")
    third_party = any(row.get("is_third_party") == "yes" for row in bip_rows) or any(
        row.get("layer") == "third_party_context" or row.get("edge_type") != "borrower_to_lender" for row in edge_rows
    )
    normalized_amount = any(row.get("normalized_amount_hs") for row in amount_rows)

    full_text = " ".join([text, mechanism.lower(), analysis_loan_type.lower()])
    refinancing = mechanism == "refinancing/versura" or contains_any(full_text, REFI_TERMS)
    repayment = mechanism == "repayment pressure" or contains_any(full_text, REPAYMENT_TERMS)
    account = mechanism == "account/nomina" or contains_any(full_text, SUPPORT_TERMS[:5])
    surety = mechanism == "surety" or contains_any(full_text, SUPPORT_TERMS[5:])
    support = account or surety or third_party

    score = min(5, (3 if refinancing else 0) + (2 if repayment else 0) + (1 if support else 0))
    terms = matched_terms(full_text, REFI_TERMS + REPAYMENT_TERMS + SUPPORT_TERMS)
    if third_party:
        terms.append("third-party context")
    reasons = []
    if refinancing:
        reasons.append("refinancing/versura signal")
    if repayment:
        reasons.append("repayment-pressure signal")
    if account:
        reasons.append("account/nomina liquidity signal")
    if surety:
        reasons.append("surety/guarantee pressure signal")
    if third_party:
        reasons.append("third-party/context dependency")
    if normalized_amount:
        reasons.append("normalized amount available")

    confidence = canonical_row.get("confidence") or first_nonblank([row.get("confidence", "") for row in bip_rows])
    scope = first_nonblank([row.get("scope_type", "") for row in bip_rows], "unknown")
    support_tier = first_nonblank([row.get("source_support_tier", "") for row in bip_rows], "unknown")
    period = first_nonblank([row.get("date_period", "") for row in bip_rows], "unknown")
    strict = (
        score > 0
        and confidence == "high"
        and period == "ciceronian_period"
        and support_tier == "Latin-controlled"
        and scope in {"private", "household"}
    )

    return {
        "episode_group": first_nonblank([row.get("episode_group", "") for row in bip_rows], "unassigned"),
        "year_bce": first_nonblank([row.get("year_bce", "") for row in bip_rows]),
        "confidence": confidence,
        "scope_type": scope,
        "source_support_tier": support_tier,
        "date_period": period,
        "mechanism_type": mechanism,
        "analysis_loan_type": analysis_loan_type,
        "stress_flag": "yes" if score > 0 else "no",
        "stress_intensity_score": str(score),
        "stress_intensity_class": stress_class(score),
        "refinancing_flag": "yes" if refinancing else "no",
        "repayment_pressure_flag": "yes" if repayment else "no",
        "account_liquidity_flag": "yes" if account else "no",
        "surety_pressure_flag": "yes" if surety else "no",
        "third_party_dependency_flag": "yes" if third_party else "no",
        "normalized_amount_flag": "yes" if normalized_amount else "no",
        "strict_slice_flag": "yes" if strict else "no",
        "stress_evidence_terms": join_sorted(terms),
        "stress_rationale": "; ".join(reasons) if reasons else "no liquidity-stress signal under current rules",
    }


def build_record_rows(
    canonical_rows: list[dict[str, str]],
    bip_by_record: dict[str, list[dict[str, str]]],
    amounts_by_record: dict[str, list[dict[str, str]]],
    edges_by_record: dict[str, list[dict[str, str]]],
) -> list[dict[str, object]]:
    rows = []
    for canonical_row in canonical_rows:
        record_id = canonical_id(canonical_row)
        meta = record_metadata(
            canonical_row,
            bip_by_record.get(record_id, []),
            amounts_by_record.get(record_id, []),
            edges_by_record.get(record_id, []),
        )
        rows.append(
            {
                "record_id": record_id,
                "source_letter_id": canonical_row.get("source_letter_id") or canonical_row.get("ancient_source_citation", ""),
                "status": canonical_row.get("status", ""),
                "latin_evidence": canonical_row.get("latin_evidence", ""),
                "english_evidence": canonical_row.get("english_evidence", ""),
                "interpretive_note": canonical_row.get("interpretive_note", ""),
                **meta,
            }
        )
    return sorted(rows, key=lambda row: str(row["record_id"]))


def index_edges_by_record(edge_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in edge_rows:
        for record_id in split_values(row.get("records", "")):
            out[record_id].append(row)
    return out


def build_role_table(
    role: str,
    bip_rows: list[dict[str, str]],
    stress_by_record: dict[str, dict[str, object]],
    stress_context_edges_by_node: Counter[str],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in bip_rows:
        if role == "intermediary":
            if row.get("is_third_party") != "yes":
                continue
        elif row.get("role_type") != role:
            continue
        record = stress_by_record.get(row["record_id"])
        if not record or record["stress_flag"] != "yes":
            continue
        node_id = row["node_id"]
        item = grouped.setdefault(
            node_id,
            {
                "canonical_name": row["canonical_name"],
                "node_id": node_id,
                "records": set(),
                "high_records": set(),
                "strict_high": set(),
                "scores": [],
                "refi": set(),
                "repayment": set(),
                "roles": Counter(),
                "mechanisms": Counter(),
                "third_dep": set(),
            },
        )
        record_id = row["record_id"]
        score = as_int(record["stress_intensity_score"])
        item["records"].add(record_id)  # type: ignore[union-attr]
        item["scores"].append(score)  # type: ignore[union-attr]
        item["roles"][row["role_type"]] += 1  # type: ignore[index]
        item["mechanisms"][str(record["mechanism_type"])] += 1  # type: ignore[index]
        if score >= 4:
            item["high_records"].add(record_id)  # type: ignore[union-attr]
        if score >= 4 and record["strict_slice_flag"] == "yes":
            item["strict_high"].add(record_id)  # type: ignore[union-attr]
        if record["refinancing_flag"] == "yes":
            item["refi"].add(record_id)  # type: ignore[union-attr]
        if record["repayment_pressure_flag"] == "yes":
            item["repayment"].add(record_id)  # type: ignore[union-attr]
        if record["third_party_dependency_flag"] == "yes":
            item["third_dep"].add(record_id)  # type: ignore[union-attr]

    rows = []
    for item in grouped.values():
        records = item["records"]  # type: ignore[assignment]
        scores = item["scores"]  # type: ignore[assignment]
        rows.append(
            {
                "canonical_name": item["canonical_name"],
                "node_id": item["node_id"],
                "high_stress_record_count": len(item["high_records"]),  # type: ignore[arg-type]
                "all_stress_record_count": len(records),
                "average_stress_score": fmt(sum(scores) / len(scores) if scores else 0),
                "max_stress_score": max(scores) if scores else 0,
                "refinancing_record_count": len(item["refi"]),  # type: ignore[arg-type]
                "repayment_pressure_record_count": len(item["repayment"]),  # type: ignore[arg-type]
                "strict_slice_high_stress_count": len(item["strict_high"]),  # type: ignore[arg-type]
                "role_mix": top_counts(item["roles"], 8),  # type: ignore[arg-type]
                "mechanism_mix": top_counts(item["mechanisms"], 8),  # type: ignore[arg-type]
                "stress_context_edge_count": stress_context_edges_by_node[str(item["node_id"])],
                "third_party_dependency_record_count": len(item["third_dep"]),  # type: ignore[arg-type]
                "supporting_records": join_sorted(records),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -as_int(row["high_stress_record_count"]),
            -as_int(row["all_stress_record_count"]),
            -as_float(row["average_stress_score"]),
            str(row["canonical_name"]),
        ),
    )


def build_all_role_table(
    bip_rows: list[dict[str, str]],
    stress_by_record: dict[str, dict[str, object]],
    stress_context_edges_by_node: Counter[str],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in bip_rows:
        record = stress_by_record.get(row["record_id"])
        if not record or record["stress_flag"] != "yes":
            continue
        node_id = row["node_id"]
        item = grouped.setdefault(
            node_id,
            {
                "canonical_name": row["canonical_name"],
                "node_id": node_id,
                "records": set(),
                "high_records": set(),
                "strict_high": set(),
                "scores": [],
                "refi": set(),
                "repayment": set(),
                "roles": Counter(),
                "mechanisms": Counter(),
                "third_dep": set(),
            },
        )
        record_id = row["record_id"]
        score = as_int(record["stress_intensity_score"])
        item["records"].add(record_id)  # type: ignore[union-attr]
        item["scores"].append(score)  # type: ignore[union-attr]
        item["roles"][row["role_type"]] += 1  # type: ignore[index]
        item["mechanisms"][str(record["mechanism_type"])] += 1  # type: ignore[index]
        if score >= 4:
            item["high_records"].add(record_id)  # type: ignore[union-attr]
        if score >= 4 and record["strict_slice_flag"] == "yes":
            item["strict_high"].add(record_id)  # type: ignore[union-attr]
        if record["refinancing_flag"] == "yes":
            item["refi"].add(record_id)  # type: ignore[union-attr]
        if record["repayment_pressure_flag"] == "yes":
            item["repayment"].add(record_id)  # type: ignore[union-attr]
        if record["third_party_dependency_flag"] == "yes":
            item["third_dep"].add(record_id)  # type: ignore[union-attr]
    return build_role_rows_from_grouped(grouped, stress_context_edges_by_node)


def build_role_rows_from_grouped(
    grouped: dict[str, dict[str, object]], stress_context_edges_by_node: Counter[str]
) -> list[dict[str, object]]:
    rows = []
    for item in grouped.values():
        records = item["records"]  # type: ignore[assignment]
        scores = item["scores"]  # type: ignore[assignment]
        rows.append(
            {
                "canonical_name": item["canonical_name"],
                "node_id": item["node_id"],
                "high_stress_record_count": len(item["high_records"]),  # type: ignore[arg-type]
                "all_stress_record_count": len(records),
                "average_stress_score": fmt(sum(scores) / len(scores) if scores else 0),
                "max_stress_score": max(scores) if scores else 0,
                "refinancing_record_count": len(item["refi"]),  # type: ignore[arg-type]
                "repayment_pressure_record_count": len(item["repayment"]),  # type: ignore[arg-type]
                "strict_slice_high_stress_count": len(item["strict_high"]),  # type: ignore[arg-type]
                "role_mix": top_counts(item["roles"], 8),  # type: ignore[arg-type]
                "mechanism_mix": top_counts(item["mechanisms"], 8),  # type: ignore[arg-type]
                "stress_context_edge_count": stress_context_edges_by_node[str(item["node_id"])],
                "third_party_dependency_record_count": len(item["third_dep"]),  # type: ignore[arg-type]
                "supporting_records": join_sorted(records),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -as_int(row["high_stress_record_count"]),
            -as_int(row["all_stress_record_count"]),
            -as_float(row["average_stress_score"]),
            str(row["canonical_name"]),
        ),
    )


def build_amount_rows(
    amount_rows: list[dict[str, str]], stress_by_record: dict[str, dict[str, object]]
) -> list[dict[str, object]]:
    rows = []
    for amount in amount_rows:
        record = stress_by_record.get(amount["record_id"])
        if not record or record["stress_flag"] != "yes":
            continue
        rows.append(
            {
                "record_id": amount["record_id"],
                "amount_instance_id": amount["amount_instance_id"],
                "source_letter_id": amount["source_letter_id"],
                "episode_group": record["episode_group"],
                "borrower": amount["borrower"],
                "lender": amount["lender"],
                "mechanism_type": record["mechanism_type"],
                "stress_intensity_score": record["stress_intensity_score"],
                "stress_intensity_class": record["stress_intensity_class"],
                "amount_role": amount["amount_role"],
                "amount_original": amount["amount_original"],
                "normalized_amount_hs": amount["normalized_amount_hs"],
                "include_in_scale_strict": amount["include_in_scale_strict"],
                "include_in_scale_candidate": amount["include_in_scale_candidate"],
                "normalization_certainty": amount["normalization_certainty"],
                "exclusion_reason": amount["exclusion_reason"],
            }
        )
    return sorted(rows, key=lambda row: (str(row["record_id"]), str(row["amount_instance_id"])))


def top_actor_names(
    bip_rows: list[dict[str, str]], records: set[str], role: str, limit: int = 5
) -> str:
    counts = Counter()
    for row in bip_rows:
        if row["record_id"] not in records:
            continue
        if role == "intermediary":
            if row.get("is_third_party") == "yes":
                counts[row["canonical_name"]] += 1
        elif row.get("role_type") == role:
            counts[row["canonical_name"]] += 1
    return top_counts(counts, limit)


def build_episode_rows(
    stress_rows: list[dict[str, object]],
    bip_rows: list[dict[str, str]],
    amount_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    stress_by_record = {str(row["record_id"]): row for row in stress_rows}
    amounts_by_record = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in stress_rows:
        if row["stress_flag"] == "yes":
            grouped[str(row["episode_group"])].append(row)
    output = []
    for episode, rows in grouped.items():
        records = {str(row["record_id"]) for row in rows}
        scores = [as_int(row["stress_intensity_score"]) for row in rows]
        mechanisms = Counter(str(row["mechanism_type"]) for row in rows)
        episode_amounts = [amount for record_id in records for amount in amounts_by_record.get(record_id, [])]
        output.append(
            {
                "episode_group": episode,
                "stress_record_count": len(rows),
                "high_stress_record_count": sum(1 for score in scores if score >= 4),
                "average_stress_score": fmt(sum(scores) / len(scores) if scores else 0),
                "max_stress_score": max(scores) if scores else 0,
                "dominant_stress_mechanism": top_counts(mechanisms, 3),
                "top_stressed_borrowers": top_actor_names(bip_rows, records, "borrower"),
                "top_creditors_or_pressure_sources": top_actor_names(bip_rows, records, "lender"),
                "top_intermediaries": top_actor_names(bip_rows, records, "intermediary"),
                "normalized_amount_count": sum(1 for amount in episode_amounts if amount.get("normalized_amount_hs")),
                "strict_hs_total": amount_sum(episode_amounts, "include_in_scale_strict"),
                "candidate_hs_total": amount_sum(episode_amounts, "include_in_scale_candidate"),
                "supporting_records": join_sorted(records),
            }
        )
    return sorted(output, key=lambda row: (-as_int(row["high_stress_record_count"]), str(row["episode_group"])))


def build_year_rows(stress_rows: list[dict[str, object]], amount_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    amounts_by_record = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in stress_rows:
        grouped[str(row["year_bce"] or "undated")].append(row)
    out = []
    for year, rows in grouped.items():
        stress_records = [row for row in rows if row["stress_flag"] == "yes"]
        records = {str(row["record_id"]) for row in stress_records}
        year_amounts = [amount for record_id in records for amount in amounts_by_record.get(record_id, [])]
        out.append(
            {
                "year_bce": year,
                "canonical_record_count": len(rows),
                "stress_record_count": len(stress_records),
                "high_stress_record_count": sum(as_int(row["stress_intensity_score"]) >= 4 for row in stress_records),
                "strict_stress_record_count": sum(row["strict_slice_flag"] == "yes" for row in stress_records),
                "refinancing_record_count": sum(row["refinancing_flag"] == "yes" for row in stress_records),
                "repayment_pressure_record_count": sum(row["repayment_pressure_flag"] == "yes" for row in stress_records),
                "normalized_amount_count": sum(1 for amount in year_amounts if amount.get("normalized_amount_hs")),
                "strict_hs_total": amount_sum(year_amounts, "include_in_scale_strict"),
                "candidate_hs_total": amount_sum(year_amounts, "include_in_scale_candidate"),
                "supporting_records": join_sorted(records),
            }
        )
    return sorted(out, key=lambda row: (9999 if row["year_bce"] == "undated" else -as_int(row["year_bce"])))


def build_scope_rows(stress_rows: list[dict[str, object]], amount_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    amounts_by_record = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)

    slices = [
        ("broad_canonical", lambda row: True, "all canonical records"),
        ("ciceronian_period_only", lambda row: row["date_period"] == "ciceronian_period", "date_period == ciceronian_period"),
        ("latin_controlled_only", lambda row: row["source_support_tier"] == "Latin-controlled", "source_support_tier == Latin-controlled"),
        ("high_confidence_only", lambda row: row["confidence"] == "high", "confidence == high"),
        ("private_household_only", lambda row: row["scope_type"] in {"private", "household"}, "scope_type in private/household"),
        (
            "strict_combined_slice",
            lambda row: row["strict_slice_flag"] == "yes" or (
                row["confidence"] == "high"
                and row["date_period"] == "ciceronian_period"
                and row["source_support_tier"] == "Latin-controlled"
                and row["scope_type"] in {"private", "household"}
            ),
            "ciceronian + Latin-controlled + high confidence + private/household",
        ),
    ]
    out = []
    for name, predicate, rule in slices:
        rows = [row for row in stress_rows if predicate(row)]
        stress = [row for row in rows if row["stress_flag"] == "yes"]
        records = {str(row["record_id"]) for row in stress}
        slice_amounts = [amount for record_id in records for amount in amounts_by_record.get(record_id, [])]
        out.append(
            {
                "slice_name": name,
                "record_count": len(rows),
                "stress_record_count": len(stress),
                "high_stress_record_count": sum(as_int(row["stress_intensity_score"]) >= 4 for row in stress),
                "refinancing_record_count": sum(row["refinancing_flag"] == "yes" for row in stress),
                "repayment_pressure_record_count": sum(row["repayment_pressure_flag"] == "yes" for row in stress),
                "strict_hs_total": amount_sum(slice_amounts, "include_in_scale_strict"),
                "candidate_hs_total": amount_sum(slice_amounts, "include_in_scale_candidate"),
                "slice_rule": rule,
            }
        )
    return out


def filter_edge_records(
    edge: dict[str, str], selected_records: set[str], stress_by_record: dict[str, dict[str, object]]
) -> dict[str, object] | None:
    records = [record for record in split_values(edge.get("records", "")) if record in selected_records]
    if not records:
        return None
    out: dict[str, object] = dict(edge)
    out["records"] = "; ".join(records)
    out["record_count"] = len(records)
    out["weight"] = len(records)
    out["episode_count"] = len({str(stress_by_record[record]["episode_group"]) for record in records if record in stress_by_record})
    out["episode_groups"] = join_sorted({str(stress_by_record[record]["episode_group"]) for record in records if record in stress_by_record})
    out["confidence_values"] = join_sorted({str(stress_by_record[record]["confidence"]) for record in records if record in stress_by_record})
    return out


def build_graph_variants(
    edge_rows: list[dict[str, str]], stress_by_record: dict[str, dict[str, object]]
) -> dict[str, list[dict[str, object]]]:
    stress_records = {record_id for record_id, row in stress_by_record.items() if row["stress_flag"] == "yes"}
    high_records = {record_id for record_id, row in stress_by_record.items() if as_int(row["stress_intensity_score"]) >= 4}
    refi_records = {record_id for record_id, row in stress_by_record.items() if row["refinancing_flag"] == "yes"}
    repay_records = {record_id for record_id, row in stress_by_record.items() if row["repayment_pressure_flag"] == "yes"}
    strict_records = {record_id for record_id, row in stress_by_record.items() if row["strict_slice_flag"] == "yes"}

    definitions = {
        "stress_records_graph": (stress_records, lambda edge: True),
        "high_stress_graph": (high_records, lambda edge: True),
        "refinancing_graph": (refi_records, lambda edge: True),
        "repayment_pressure_graph": (repay_records, lambda edge: True),
        "stress_direct_only_graph": (stress_records, lambda edge: edge.get("edge_type") == "borrower_to_lender"),
        "stress_context_graph": (stress_records, lambda edge: edge.get("edge_type") != "borrower_to_lender"),
        "strict_stress_graph": (strict_records, lambda edge: True),
    }
    variants: dict[str, list[dict[str, object]]] = {}
    for name, (records, edge_predicate) in definitions.items():
        rows = []
        for edge in edge_rows:
            if not edge_predicate(edge):
                continue
            filtered = filter_edge_records(edge, records, stress_by_record)
            if filtered:
                rows.append(filtered)
        variants[name] = rows
    return variants


def graph_metrics(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    adjacency: dict[str, Counter[str]] = defaultdict(Counter)
    names: dict[str, str] = {}
    direct_degree = Counter()
    context_degree = Counter()
    for edge in edges:
        source = str(edge["source_id"])
        target = str(edge["target_id"])
        weight = as_int(edge.get("weight", 1)) or 1
        adjacency[source][target] += weight
        adjacency[target][source] += weight
        names[source] = str(edge.get("source_name", source))
        names[target] = str(edge.get("target_name", target))
        if edge.get("edge_type") == "borrower_to_lender":
            direct_degree[source] += weight
            direct_degree[target] += weight
        else:
            context_degree[source] += weight
            context_degree[target] += weight

    nodes = sorted(adjacency)
    if not nodes:
        return []
    component_sizes = {}
    seen = set()
    for node in nodes:
        if node in seen:
            continue
        queue = deque([node])
        component = set()
        seen.add(node)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        for member in component:
            component_sizes[member] = len(component)

    pagerank = {node: 1.0 / len(nodes) for node in nodes}
    damping = 0.85
    for _ in range(50):
        new_rank = {node: (1.0 - damping) / len(nodes) for node in nodes}
        for node in nodes:
            total_weight = sum(adjacency[node].values())
            if total_weight == 0:
                continue
            for neighbor, weight in adjacency[node].items():
                new_rank[neighbor] += damping * pagerank[node] * (weight / total_weight)
        if sum(abs(new_rank[node] - pagerank[node]) for node in nodes) < 1e-10:
            pagerank = new_rank
            break
        pagerank = new_rank

    betweenness = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack = []
        predecessors = {node: [] for node in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        distance = dict.fromkeys(nodes, -1)
        sigma[source] = 1.0
        distance[source] = 0
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbor in adjacency[vertex]:
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[vertex] + 1
                if distance[neighbor] == distance[vertex] + 1:
                    sigma[neighbor] += sigma[vertex]
                    predecessors[neighbor].append(vertex)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            vertex = stack.pop()
            for pred in predecessors[vertex]:
                if sigma[vertex]:
                    delta[pred] += (sigma[pred] / sigma[vertex]) * (1.0 + delta[vertex])
            if vertex != source:
                betweenness[vertex] += delta[vertex]
    if len(nodes) > 2:
        scale = 1 / ((len(nodes) - 1) * (len(nodes) - 2))
        for node in nodes:
            betweenness[node] *= scale

    rows = []
    for node in nodes:
        rows.append(
            {
                "node_id": node,
                "canonical_name": names.get(node, node),
                "weighted_degree": sum(adjacency[node].values()),
                "direct_edge_degree": direct_degree[node],
                "context_edge_degree": context_degree[node],
                "component_size": component_sizes.get(node, 1),
                "pagerank": pagerank[node],
                "betweenness": betweenness[node],
            }
        )
    ranked = sorted(rows, key=lambda row: (-as_float(row["pagerank"]), -as_float(row["weighted_degree"]), row["canonical_name"]))
    for rank, row in enumerate(ranked, start=1):
        row["centrality_rank"] = rank
    return ranked


def build_delta_rows(
    centrality_by_variant: dict[str, list[dict[str, object]]], full_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    full_by_node = {str(row["node_id"]): row for row in full_rows}
    rows = []
    for variant, centrality_rows in centrality_by_variant.items():
        for row in centrality_rows:
            full = full_by_node.get(str(row["node_id"]), {})
            full_rank = as_int(full.get("centrality_rank", 0))
            stress_rank = as_int(row.get("centrality_rank", 0))
            rows.append(
                {
                    "variant_name": variant,
                    "node_id": row["node_id"],
                    "canonical_name": row["canonical_name"],
                    "full_graph_rank": full_rank,
                    "stress_graph_rank": stress_rank,
                    "rank_delta": full_rank - stress_rank if full_rank and stress_rank else "",
                    "full_weighted_degree": full.get("weighted_degree", 0),
                    "stress_weighted_degree": row.get("weighted_degree", 0),
                    "degree_delta": as_float(row.get("weighted_degree", 0)) - as_float(full.get("weighted_degree", 0)),
                    "full_betweenness": fmt(as_float(full.get("betweenness", 0)), 6),
                    "stress_betweenness": fmt(as_float(row.get("betweenness", 0)), 6),
                    "betweenness_delta": fmt(as_float(row.get("betweenness", 0)) - as_float(full.get("betweenness", 0)), 6),
                }
            )
    return sorted(rows, key=lambda row: (row["variant_name"], as_int(row["stress_graph_rank"])))


def write_graph_outputs(
    edge_rows: list[dict[str, str]], stress_by_record: dict[str, dict[str, object]]
) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, object]]]:
    variants = build_graph_variants(edge_rows, stress_by_record)
    fieldnames = list(edge_rows[0].keys()) if edge_rows else []
    for name, rows in variants.items():
        write_rows(GRAPH_VARIANTS / f"{name}.csv", fieldnames, rows)

    full_metrics = graph_metrics([dict(row) for row in edge_rows])
    centrality_by_variant = {name: graph_metrics(rows) for name, rows in variants.items()}
    centrality_rows = []
    for variant, rows in centrality_by_variant.items():
        for row in rows:
            centrality_rows.append({"variant_name": variant, **row})
    write_rows(TABLES / "liquidity_stress_graph_centrality.csv", CENTRALITY_FIELDS, centrality_rows)
    delta_rows = build_delta_rows(centrality_by_variant, full_metrics)
    write_rows(TABLES / "liquidity_stress_graph_centrality_delta.csv", DELTA_FIELDS, delta_rows)
    return variants, centrality_rows


def build_mechanism_rows(
    stress_rows: list[dict[str, object]], amount_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    fields = [
        "mechanism_type",
        "record_count",
        "stress_record_count",
        "stress_share",
        "high_stress_record_count",
        "strict_slice_stress_record_count",
        "normalized_amount_count",
        "strict_hs_total",
        "candidate_hs_total",
        "supporting_records",
    ]
    amounts_by_record = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in stress_rows:
        grouped[str(row["mechanism_type"])].append(row)
    output = []
    for mechanism, rows in grouped.items():
        stress = [row for row in rows if row["stress_flag"] == "yes"]
        records = {str(row["record_id"]) for row in stress}
        mechanism_amounts = [amount for record_id in records for amount in amounts_by_record.get(record_id, [])]
        output.append(
            {
                "mechanism_type": mechanism,
                "record_count": len(rows),
                "stress_record_count": len(stress),
                "stress_share": fmt(len(stress) / len(rows) if rows else 0),
                "high_stress_record_count": sum(as_int(row["stress_intensity_score"]) >= 4 for row in stress),
                "strict_slice_stress_record_count": sum(row["strict_slice_flag"] == "yes" for row in stress),
                "normalized_amount_count": sum(1 for amount in mechanism_amounts if amount.get("normalized_amount_hs")),
                "strict_hs_total": amount_sum(mechanism_amounts, "include_in_scale_strict"),
                "candidate_hs_total": amount_sum(mechanism_amounts, "include_in_scale_candidate"),
                "supporting_records": join_sorted(records),
            }
        )
    write_rows(TABLES / "liquidity_stress_by_mechanism.csv", fields, sorted(output, key=lambda row: -as_int(row["stress_record_count"])))
    return output


def fallback_types_for_record(row: dict[str, object]) -> set[str]:
    text = " ".join(
        [
            str(row.get("mechanism_type", "")),
            str(row.get("analysis_loan_type", "")),
            str(row.get("status", "")),
            str(row.get("latin_evidence", "")),
            str(row.get("english_evidence", "")),
            str(row.get("interpretive_note", "")),
            str(row.get("stress_evidence_terms", "")),
        ]
    ).lower()
    fallback_types = set()
    if row.get("refinancing_flag") == "yes" or contains_any(text, REFI_TERMS):
        fallback_types.add("new_borrowing_or_versura")
    if row.get("repayment_pressure_flag") == "yes" or contains_any(text, FAILED_SOURCE_TERMS):
        fallback_types.add("collection_from_debtor_or_failed_source")
    if contains_any(text, SALE_TERMS):
        fallback_types.add("sale_fallback")
    if row.get("account_liquidity_flag") == "yes":
        fallback_types.add("account_or_nomen_transfer")
    if row.get("surety_pressure_flag") == "yes":
        fallback_types.add("surety_or_security")
    if row.get("third_party_dependency_flag") == "yes":
        fallback_types.add("friend_or_agent_intermediation")
    return fallback_types


def chain_class(score: int) -> str:
    if score >= 7:
        return "acute_chain_stress"
    if score >= 5:
        return "significant_chain_stress"
    if score >= 3:
        return "moderate_liquidity_management"
    return "weak_or_isolated_chain_signal"


def build_refinancing_chain_rows(
    stress_rows: list[dict[str, object]],
    bip_rows: list[dict[str, str]],
    amount_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    amounts_by_record = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    record_fallbacks = {str(row["record_id"]): fallback_types_for_record(row) for row in stress_rows}
    for row in stress_rows:
        fallbacks = record_fallbacks[str(row["record_id"])]
        if row["stress_flag"] == "yes" and (
            row["refinancing_flag"] == "yes"
            or row["repayment_pressure_flag"] == "yes"
            or len(fallbacks) >= 2
            or as_int(row["stress_intensity_score"]) >= 4
        ):
            episode = str(row["episode_group"] or "unassigned")
            if episode in {"Other/private credit", "unassigned"}:
                source = str(row.get("source_letter_id") or row.get("record_id") or "unassigned")
                episode = f"{episode}: {source}"
            grouped[episode].append(row)

    chain_rows = []
    detail_rows = []
    chain_record_ids: set[str] = set()
    chain_index = 1
    for episode, rows in sorted(grouped.items(), key=lambda item: item[0]):
        records = {str(row["record_id"]) for row in rows}
        all_fallbacks = set().union(*(record_fallbacks[str(row["record_id"])] for row in rows))
        has_refi = any(row["refinancing_flag"] == "yes" for row in rows)
        has_repayment = any(row["repayment_pressure_flag"] == "yes" for row in rows)
        has_account = any(row["account_liquidity_flag"] == "yes" for row in rows)
        has_surety = any(row["surety_pressure_flag"] == "yes" for row in rows)
        has_third_party = any(row["third_party_dependency_flag"] == "yes" for row in rows)
        has_sale = "sale_fallback" in all_fallbacks
        has_failed_source = "collection_from_debtor_or_failed_source" in all_fallbacks
        years = sorted({as_int(row["year_bce"]) for row in rows if as_int(row["year_bce"])})
        letters = join_sorted({str(row["source_letter_id"]) for row in rows})
        episode_amounts = [amount for record_id in records for amount in amounts_by_record.get(record_id, [])]
        normalized_amounts = [amount for amount in episode_amounts if amount.get("normalized_amount_hs")]
        score = (
            (2 if has_refi else 0)
            + (2 if has_failed_source else 0)
            + (1 if has_sale else 0)
            + (1 if has_account else 0)
            + (1 if has_surety else 0)
            + (1 if has_third_party else 0)
            + (1 if len(rows) >= 2 else 0)
            + (1 if len({str(row["source_letter_id"]) for row in rows}) >= 2 else 0)
        )
        if not has_refi and score < 4:
            continue
        chain_id = f"O4-CHAIN-{chain_index:03d}"
        chain_index += 1
        chain_record_ids.update(records)
        latin_anchors = " | ".join(compact_text(str(row.get("latin_evidence", "")), 115) for row in rows[:4] if row.get("latin_evidence"))
        chain_rows.append(
            {
                "chain_id": chain_id,
                "episode_group": episode,
                "date_window": f"{max(years)}-{min(years)} BCE" if len(years) > 1 else (f"{years[0]} BCE" if years else "undated"),
                "supporting_record_ids": join_sorted(records),
                "supporting_letters": letters,
                "primary_stressed_actors": actor_names_for_records(bip_rows, records, "borrower"),
                "creditors_or_pressure_sources": actor_names_for_records(bip_rows, records, "lender"),
                "intermediaries": actor_names_for_records(bip_rows, records, "intermediary"),
                "fallback_types": join_sorted(all_fallbacks),
                "versura_flag": "yes" if has_refi else "no",
                "failed_or_uncertain_source_flag": "yes" if has_failed_source else "no",
                "sale_fallback_flag": "yes" if has_sale else "no",
                "account_transfer_flag": "yes" if has_account else "no",
                "surety_flag": "yes" if has_surety else "no",
                "repayment_pressure_flag": "yes" if has_repayment else "no",
                "third_party_dependency_flag": "yes" if has_third_party else "no",
                "record_count": len(rows),
                "high_stress_record_count": sum(as_int(row["stress_intensity_score"]) >= 4 for row in rows),
                "normalized_amount_count": len(normalized_amounts),
                "strict_hs_total": amount_sum(episode_amounts, "include_in_scale_strict"),
                "candidate_hs_total": amount_sum(episode_amounts, "include_in_scale_candidate"),
                "chain_intensity_score": score,
                "chain_class": chain_class(score),
                "latin_anchors": latin_anchors,
                "interpretive_note": "Episode-level chain inferred from repeated stress/fallback signals; use supporting records for Latin-controlled prose.",
                "confidence": "high" if all(row["confidence"] == "high" for row in rows) else "medium",
                "followup_needed": "yes",
            }
        )
        for row in rows:
            record_id = str(row["record_id"])
            detail_rows.append(
                {
                    "chain_id": chain_id,
                    "record_id": record_id,
                    "source_letter_id": row["source_letter_id"],
                    "episode_group": episode,
                    "year_bce": row["year_bce"],
                    "borrower_or_stressed_actor": actor_names_for_record(bip_rows, record_id, "borrower"),
                    "creditor_or_pressure_source": actor_names_for_record(bip_rows, record_id, "lender"),
                    "intermediaries": actor_names_for_record(bip_rows, record_id, "intermediary"),
                    "mechanism_type": row["mechanism_type"],
                    "stress_intensity_score": row["stress_intensity_score"],
                    "stress_intensity_class": row["stress_intensity_class"],
                    "fallback_types": join_sorted(record_fallbacks[record_id]),
                    "status": row["status"],
                    "latin_evidence": row["latin_evidence"],
                    "stress_rationale": row["stress_rationale"],
                }
            )
    return (
        sorted(chain_rows, key=lambda row: (-as_int(row["chain_intensity_score"]), str(row["episode_group"]))),
        sorted(detail_rows, key=lambda row: (str(row["chain_id"]), str(row["record_id"]))),
        chain_record_ids,
    )


def write_chain_graph(edge_rows: list[dict[str, str]], chain_record_ids: set[str]) -> list[dict[str, object]]:
    rows = []
    for edge in edge_rows:
        filtered_records = [record for record in split_values(edge.get("records", "")) if record in chain_record_ids]
        if not filtered_records:
            continue
        out: dict[str, object] = dict(edge)
        out["records"] = "; ".join(filtered_records)
        out["record_count"] = len(filtered_records)
        out["weight"] = len(filtered_records)
        rows.append(out)
    write_rows(TABLES / "graph_variants" / "refinancing_chain_graph.csv", list(edge_rows[0].keys()) if edge_rows else [], rows)
    return rows


def build_evidence_rows(
    stress_rows: list[dict[str, object]],
    borrower_rows: list[dict[str, object]],
    lender_rows: list[dict[str, object]],
    intermediary_rows: list[dict[str, object]],
    variants: dict[str, list[dict[str, object]]],
    chain_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    refi = [row for row in stress_rows if row["refinancing_flag"] == "yes"]
    repayment = [row for row in stress_rows if row["repayment_pressure_flag"] == "yes"]
    indirect = [row for row in stress_rows if row["account_liquidity_flag"] == "yes" or row["surety_pressure_flag"] == "yes"]
    stress = [row for row in stress_rows if row["stress_flag"] == "yes"]
    context_edges = len(variants.get("stress_context_graph", []))
    direct_edges = len(variants.get("stress_direct_only_graph", []))
    acute_chains = [row for row in chain_rows if row["chain_class"] == "acute_chain_stress"]
    return [
        {
            "claim_id": "OBJ4-C1",
            "claim_text": "Refinancing/versura records form a distinct high-pressure subset of the Objective 04 stress corpus.",
            "supporting_record_ids": join_sorted({str(row["record_id"]) for row in refi}),
            "supporting_outputs": "tables/liquidity_stress_records.csv; tables/liquidity_stress_by_mechanism.csv",
            "episode_id": "aggregate",
            "mechanism": "refinancing/versura",
            "confidence": "medium",
            "caveat": "Mechanism labels are interpretive and major examples should remain Latin-controlled in prose.",
            "followup_needed": "Yes",
        },
        {
            "claim_id": "OBJ4-C2",
            "claim_text": "Repayment pressure is analytically separate from refinancing pressure.",
            "supporting_record_ids": join_sorted({str(row["record_id"]) for row in repayment}),
            "supporting_outputs": "tables/liquidity_stress_records.csv; tables/liquidity_stress_by_mechanism.csv",
            "episode_id": "aggregate",
            "mechanism": "repayment pressure",
            "confidence": "medium",
            "caveat": "Some records include both payment pressure and mediated/account handling.",
            "followup_needed": "Yes",
        },
        {
            "claim_id": "OBJ4-C3",
            "claim_text": "Account/nomina and surety signals often mark indirect liquidity management rather than simple bilateral loans.",
            "supporting_record_ids": join_sorted({str(row["record_id"]) for row in indirect}),
            "supporting_outputs": "tables/liquidity_stress_records.csv; tables/liquidity_stress_by_intermediary.csv",
            "episode_id": "aggregate",
            "mechanism": "account/nomina; surety",
            "confidence": "medium",
            "caveat": "The coding identifies mechanism signals, not legal priority or actual cash movement.",
            "followup_needed": "Yes",
        },
        {
            "claim_id": "OBJ4-C4",
            "claim_text": f"Stress records have substantial context-edge structure: {context_edges} stress context edges versus {direct_edges} stress direct edges in the derived graph variants.",
            "supporting_record_ids": "Aggregate graph result",
            "supporting_outputs": "tables/graph_variants/stress_context_graph.csv; tables/graph_variants/stress_direct_only_graph.csv",
            "episode_id": "aggregate",
            "mechanism": "stress graph",
            "confidence": "medium",
            "caveat": "Graph edges reflect surviving textual evidence and current actor parsing.",
            "followup_needed": "No",
        },
        {
            "claim_id": "OBJ4-C5",
            "claim_text": "Borrower, lender, and intermediary rankings produce different actor lists and should not be collapsed into a single top-actor ranking.",
            "supporting_record_ids": "Aggregate actor-ranking result",
            "supporting_outputs": "tables/liquidity_stress_by_borrower.csv; tables/liquidity_stress_by_lender.csv; tables/liquidity_stress_by_intermediary.csv",
            "episode_id": "aggregate",
            "mechanism": "actor role rankings",
            "confidence": "medium",
            "caveat": "Rankings are counts of preserved records, not total historical exposure.",
            "followup_needed": "No",
        },
        {
            "claim_id": "OBJ4-C6",
            "claim_text": f"{len(chain_rows)} episode-level refinancing/liquidity chains can be reconstructed from repeated fallback signals; {len(acute_chains)} qualify as acute chain-stress cases under the chain score.",
            "supporting_record_ids": join_sorted({record for row in chain_rows for record in split_values(str(row["supporting_record_ids"]))}),
            "supporting_outputs": "tables/refinancing_chains.csv; tables/refinancing_chain_records.csv; tables/graph_variants/refinancing_chain_graph.csv",
            "episode_id": "aggregate",
            "mechanism": "refinancing chain",
            "confidence": "medium",
            "caveat": "Chain scoring is an explicit research coding device; it reconstructs dependency patterns, not cash-flow certainty.",
            "followup_needed": "Yes",
        },
    ]


def write_findings(
    stress_rows: list[dict[str, object]],
    scope_rows: list[dict[str, object]],
    borrower_rows: list[dict[str, object]],
    lender_rows: list[dict[str, object]],
    intermediary_rows: list[dict[str, object]],
    chain_rows: list[dict[str, object]],
) -> None:
    stress = [row for row in stress_rows if row["stress_flag"] == "yes"]
    high = [row for row in stress if as_int(row["stress_intensity_score"]) >= 4]
    refi = [row for row in stress if row["refinancing_flag"] == "yes"]
    repayment = [row for row in stress if row["repayment_pressure_flag"] == "yes"]
    strict = next(row for row in scope_rows if row["slice_name"] == "strict_combined_slice")
    top_borrowers = "; ".join(
        f"{row['canonical_name']} ({row['high_stress_record_count']})" for row in borrower_rows[:5]
    )
    top_lenders = "; ".join(f"{row['canonical_name']} ({row['high_stress_record_count']})" for row in lender_rows[:5])
    top_intermediaries = "; ".join(
        f"{row['canonical_name']} ({row['high_stress_record_count']})" for row in intermediary_rows[:5]
    )
    acute_chains = [row for row in chain_rows if row["chain_class"] == "acute_chain_stress"]
    significant_chains = [
        row for row in chain_rows if row["chain_class"] in {"acute_chain_stress", "significant_chain_stress"}
    ]
    top_chains = "; ".join(
        f"{row['episode_group']} ({row['chain_intensity_score']}, {row['chain_class']})" for row in chain_rows[:5]
    )
    text = f"""# Objective 04: Credit Mechanisms

## Research Question

Which Cicero/Verboven credit records and episode-level chains show liquidity stress, refinancing pressure, repayment pressure, account-based liquidity management, surety pressure, or third-party-dependent stress?

## Dataset And Filters

The headline denominator is the broad canonical dataset: {len(stress_rows)} records. Strict sensitivity uses Ciceronian-period, Latin-controlled, high-confidence, private/household rows.

Generated Objective 04 tables are in `tables/`, with stress-specific and chain-specific graph variants in `tables/graph_variants/`.

## Methods And Controls

Each canonical record receives a 0-5 liquidity-stress score. Explicit refinancing or *versura* contributes 3 points; repayment pressure, overdue/disputed status, or urgent collection language contributes 2 points; account/nomina, surety, or third-party context contributes 1 point. Scores are capped at 5.

The refinancing-chain layer groups qualifying stress records by episode. Chain scoring asks whether an episode combines explicit *versura*/refinancing, failed or uncertain expected payment, sale fallback, account/nomina transfer, surety/security, third-party intermediation, and repeated attestation across records or letters. This chain score is a transparent research coding device, not an ancient category.

Actor rankings are role-specific: borrowers/debtors, lenders/creditors, intermediaries, and all-role visibility are reported separately.

## Key Findings

1. {len(stress)} of {len(stress_rows)} canonical records have at least one liquidity-stress signal; {len(high)} are high-stress records with score >= 4.
2. Refinancing/versura appears in {len(refi)} stress records, while repayment pressure appears in {len(repayment)} stress records. These categories overlap in some cases but should remain analytically distinct.
3. The strict sensitivity slice contains {strict['stress_record_count']} stress records and {strict['high_stress_record_count']} high-stress records.
4. Top high-stress borrowers/debtors by preserved record count: {top_borrowers or 'none'}.
5. Top high-stress lenders/creditors by preserved record count: {top_lenders or 'none'}.
6. Top high-stress intermediaries/context actors by preserved record count: {top_intermediaries or 'none'}.
7. {len(chain_rows)} episode-level refinancing/liquidity chains are reconstructed in `tables/refinancing_chains.csv`; {len(significant_chains)} are significant or acute chain-stress cases, and {len(acute_chains)} are acute under the chain score.
8. Highest-scoring chain episodes: {top_chains or 'none'}.

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
"""
    (OBJ_ROOT / "findings.md").write_text(text, encoding="utf-8")


def validate_outputs(
    canonical_rows: list[dict[str, str]], stress_rows: list[dict[str, object]], variants: dict[str, list[dict[str, object]]]
) -> list[str]:
    errors = []
    canonical_ids = {canonical_id(row) for row in canonical_rows}
    output_ids = [str(row["record_id"]) for row in stress_rows]
    if len(output_ids) != len(canonical_ids):
        errors.append(f"stress row count {len(output_ids)} != canonical count {len(canonical_ids)}")
    if set(output_ids) != canonical_ids:
        errors.append("stress record IDs do not exactly match canonical record IDs")
    stress_by_record = {str(row["record_id"]): row for row in stress_rows}
    for row in variants.get("high_stress_graph", []):
        for record_id in split_values(str(row.get("records", ""))):
            if as_int(stress_by_record[record_id]["stress_intensity_score"]) < 4:
                errors.append(f"high_stress_graph contains non-high-stress record {record_id}")
    expected = {
        # ATT-PILOT-0008 was human-reviewed as a repeated mention and merged
        # into the active canonical survivor ATT-PILOT-0005.
        "ATT-PILOT-0005": ("high_refinancing_or_repayment_pressure", "yes"),
        "ATT-PILOT-0014": ("high_refinancing_or_repayment_pressure", "yes"),
        "ATT-PILOT-0018": ("high_refinancing_or_repayment_pressure", "yes"),
        "ATT-PILOT-0007": ("moderate_pressure", "no"),
        "ATT-PILOT-0003": ("high_refinancing_or_repayment_pressure", "yes"),
    }
    for record_id, (expected_class, expected_refi) in expected.items():
        row = stress_by_record.get(record_id)
        if not row:
            errors.append(f"missing expected record {record_id}")
            continue
        if row["stress_intensity_class"] != expected_class:
            errors.append(f"{record_id} class {row['stress_intensity_class']} != {expected_class}")
        if row["refinancing_flag"] != expected_refi:
            errors.append(f"{record_id} refinancing flag {row['refinancing_flag']} != {expected_refi}")
    return errors


def main() -> None:
    canonical_rows = load_rows(CANONICAL)
    bip_rows = load_rows(BIPARTITE)
    edge_rows = load_rows(EDGES)
    amount_rows = load_rows(AMOUNTS)

    bip_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bip_rows:
        bip_by_record[row["record_id"]].append(row)
    amounts_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in amount_rows:
        amounts_by_record[row["record_id"]].append(row)
    edges_by_record = index_edges_by_record(edge_rows)

    stress_rows = build_record_rows(canonical_rows, bip_by_record, amounts_by_record, edges_by_record)
    stress_by_record = {str(row["record_id"]): row for row in stress_rows}
    write_rows(TABLES / "liquidity_stress_records.csv", RECORD_FIELDS, stress_rows)

    stress_context_edges_by_node = Counter()
    for edge in edge_rows:
        if edge.get("edge_type") == "borrower_to_lender":
            continue
        if not any(stress_by_record.get(record, {}).get("stress_flag") == "yes" for record in split_values(edge.get("records", ""))):
            continue
        stress_context_edges_by_node[edge["source_id"]] += 1
        stress_context_edges_by_node[edge["target_id"]] += 1

    borrower_rows = build_role_table("borrower", bip_rows, stress_by_record, stress_context_edges_by_node)
    lender_rows = build_role_table("lender", bip_rows, stress_by_record, stress_context_edges_by_node)
    intermediary_rows = build_role_table("intermediary", bip_rows, stress_by_record, stress_context_edges_by_node)
    all_role_rows = build_all_role_table(bip_rows, stress_by_record, stress_context_edges_by_node)
    write_rows(TABLES / "liquidity_stress_by_borrower.csv", ACTOR_ROLE_FIELDS, borrower_rows)
    write_rows(TABLES / "liquidity_stress_by_lender.csv", ACTOR_ROLE_FIELDS, lender_rows)
    write_rows(TABLES / "liquidity_stress_by_intermediary.csv", ACTOR_ROLE_FIELDS, intermediary_rows)
    write_rows(TABLES / "liquidity_stress_by_actor_all_roles.csv", ACTOR_ROLE_FIELDS, all_role_rows)

    amount_output_rows = build_amount_rows(amount_rows, stress_by_record)
    write_rows(TABLES / "liquidity_stress_amounts.csv", AMOUNT_FIELDS, amount_output_rows)
    build_mechanism_rows(stress_rows, amount_rows)
    episode_rows = build_episode_rows(stress_rows, bip_rows, amount_rows)
    year_rows = build_year_rows(stress_rows, amount_rows)
    scope_rows = build_scope_rows(stress_rows, amount_rows)
    chain_rows, chain_record_rows, chain_record_ids = build_refinancing_chain_rows(stress_rows, bip_rows, amount_rows)
    write_rows(TABLES / "liquidity_stress_by_episode.csv", EPISODE_FIELDS, episode_rows)
    write_rows(TABLES / "liquidity_stress_by_year.csv", YEAR_FIELDS, year_rows)
    write_rows(TABLES / "liquidity_stress_scope_sensitivity.csv", SCOPE_FIELDS, scope_rows)
    write_rows(TABLES / "refinancing_chains.csv", CHAIN_FIELDS, chain_rows)
    write_rows(TABLES / "refinancing_chain_records.csv", CHAIN_RECORD_FIELDS, chain_record_rows)

    variants, _centrality_rows = write_graph_outputs(edge_rows, stress_by_record)
    chain_graph_rows = write_chain_graph(edge_rows, chain_record_ids)
    variants["refinancing_chain_graph"] = chain_graph_rows
    evidence_rows = build_evidence_rows(stress_rows, borrower_rows, lender_rows, intermediary_rows, variants, chain_rows)
    write_rows(OBJ_ROOT / "evidence.csv", EVIDENCE_FIELDS, evidence_rows)
    write_findings(stress_rows, scope_rows, borrower_rows, lender_rows, intermediary_rows, chain_rows)

    errors = validate_outputs(canonical_rows, stress_rows, variants)
    if errors:
        raise SystemExit("Objective 04 validation failed:\n- " + "\n- ".join(errors))
    print(f"Wrote Objective 04 liquidity-stress metrics for {len(stress_rows)} canonical records.")


if __name__ == "__main__":
    main()
