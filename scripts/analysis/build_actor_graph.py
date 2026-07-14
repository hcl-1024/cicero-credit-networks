#!/usr/bin/env python3
"""Build a curated actor graph for Cicero loan analysis."""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict, deque
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "build" / "analysis" / "core"
GRAPH_ROOT = ROOT / "build" / "analysis" / "graphs"
TABLES = GRAPH_ROOT / "tables"
FIGURES = GRAPH_ROOT / "figures"

PARTY_SOURCE = CORE / "cicero_loan_party_roles.csv"
EDGE_SOURCE = CORE / "cicero_loan_network_edges.csv"
ANALYSIS_SOURCE = CORE / "cicero_loans_analysis_ready.csv"
CANONICAL_SOURCE = ROOT / "data" / "canonical" / "cicero_credit_records.csv"
VARIANTS = TABLES / "graph_variants"

NODE_FIELDS = [
    "node_id",
    "canonical_name",
    "display_name",
    "identity_base_name",
    "identity_group",
    "identity_resolution",
    "actor_type",
    "actor_subtype",
    "certainty",
    "is_collective",
    "is_placeholder",
    "include_in_centrality",
    "record_count",
    "direct_record_count",
    "third_party_record_count",
    "episode_count",
    "borrower_count",
    "lender_count",
    "third_party_count",
    "sender_count",
    "recipient_count",
    "weighted_degree",
    "direct_edge_degree",
    "context_edge_degree",
    "confidence_values",
    "episode_groups",
    "notes",
]

EDGE_FIELDS = [
    "source_id",
    "target_id",
    "source_name",
    "target_name",
    "edge_type",
    "layer",
    "actor_role_source",
    "actor_role_target",
    "canonical_loan_type",
    "analysis_loan_type",
    "mechanism_type",
    "scope_type",
    "amount_tier",
    "source_support_tier",
    "date_period",
    "date_certainty",
    "date_min_year",
    "date_max_year",
    "weight",
    "record_count",
    "records",
    "episode_count",
    "episode_groups",
    "year_bce_values",
    "collection_values",
    "source_genre_values",
    "verification_status_values",
    "confidence_values",
]

ALIAS_FIELDS = [
    "raw_label",
    "action",
    "output_nodes",
    "reason",
    "record_ids",
    "source_fields",
    "review_status",
    "review_note",
]

EPISODE_FIELDS = [
    "episode_group",
    "record_count",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "actor_count",
    "mechanism_types",
    "scope_types",
    "analysis_loan_types",
    "confidence_values",
    "amount_tiers",
    "source_support_tiers",
    "year_bce_values",
    "date_periods",
    "top_actors",
]

BIPARTITE_FIELDS = [
    "record_id",
    "node_id",
    "canonical_name",
    "role_type",
    "role_detail",
    "is_direct_party",
    "is_third_party",
    "episode_group",
    "year_bce",
    "confidence",
    "canonical_loan_type",
    "analysis_loan_type",
    "mechanism_type",
    "scope_type",
    "amount_tier",
    "source_support_tier",
    "date_period",
    "date_certainty",
]

QUALITY_FIELDS = [
    "check_name",
    "severity",
    "status",
    "count",
    "examples",
    "recommendation",
]

VARIANT_FIELDS = [
    "variant_name",
    "description",
    "output_path",
    "node_count",
    "edge_count",
    "record_count",
    "component_count",
    "largest_component_node_count",
    "top_weighted_degree_nodes",
    "filter_recipe",
]

ACTOR_TYPE_SUMMARY_FIELDS = [
    "actor_type",
    "node_count",
    "weighted_degree",
    "direct_edge_degree",
    "context_edge_degree",
    "record_count",
    "top_nodes",
]

MECHANISM_SUMMARY_FIELDS = [
    "analysis_loan_type",
    "mechanism_type",
    "scope_type",
    "edge_count",
    "direct_edge_count",
    "third_party_context_edge_count",
    "actor_count",
    "record_count",
    "top_actors",
]

VARIANT_CENTRALITY_FIELDS = [
    "variant_name",
    "centrality_rank",
    "canonical_name",
    "weighted_degree",
    "component_size",
    "pagerank",
    "betweenness",
]


PLACEHOLDER_PATTERNS = [
    r"\bunknown\b",
    r"\bunclear\b",
    r"\bunspecified\b",
    r"\bunidentified\b",
    r"\bnot applicable\b",
    r"\bnot extracted\b",
    r"\bbiography\b",
    r"\bhistory\b",
    r"\bpoetry\b",
    r"\banalogical\b",
    r"\bhypothetical\b",
    r"\bnot individually named\b",
    r"\bpotential refinancing source\b",
    r"\bfuture versura lender\b",
    r"\bsource unspecified\b",
    r"\blender unspecified\b",
    r"\bclaimants not individually named\b",
    r"\btax/credit claimants\b",
    r"\bunnamed\b",
    r"^debtors$",
    r"\baudience\b",
    r"\breaders\b",
    r"\bjudges\b",
    r"\bjury\b",
    r"\bcourt\b",
    r"\binvestment debtors\b",
    r"\bsenators and supporters\b",
    r"\bloan terms unverified\b",
    r"\bpolitical payment\b",
    r"\bneutrality purchase\b",
    r"\bpayment/bribe\b",
    r"\bsilver bowl gift-like aid\b",
    r"\bstate or public contract\b",
    r"\bforum/professional lenders\b",
    r"\brefused large sums\b",
    r"^doctor$",
    r"^heir$",
]

SOURCE_AUTHOR_LABELS = {
    "cornelius nepos",
    "horace",
    "plutarch",
    "plutarch; appian",
    "seneca",
    "suetonius",
    "velleius paterculus",
}

COLLECTIVE_PATTERNS = [
    r"\bamici\b",
    r"\bcreditor",
    r"\bcoheir",
    r"\bcommunities\b",
    r"\bpublicani\b",
    r"\btax company\b",
    r"\bsponsores\b",
    r"\bprocurators\b",
    r"\bprocuratores\b",
    r"\bfriends\b",
    r"\bborrowers\b",
    r"\bsellers\b",
    r"\bpublic contract\b",
]

SECONDARY_FINANCE_ROLE_NOTES = {
    "cluvius": "Andreau treats Cluvius of Puteoli as a specialized intermediary for interest-bearing loans and city debt-claims, while cautioning that his precise social status is unclear.",
    "c. vestorius": "Andreau treats Vestorius of Puteoli as an intermediary through whom Atticus invested money; classify as a finance intermediary, not automatically as an argentarius banker.",
    "vestorius": "Andreau treats Vestorius of Puteoli as an intermediary through whom Atticus invested money; classify as a finance intermediary, not automatically as an argentarius banker.",
    "scaptius": "Andreau treats Scaptius with Matinius as an intermediary in the Salamis loan; Hollander also describes M. Scaptius as Brutus' agent in securing repayment.",
    "matinius": "Andreau treats Matinius with Scaptius as an intermediary in the Salamis loan, involving money belonging to Brutus.",
}

SPLIT_LABELS = {
    "brutus through procurators/straw men": ["Brutus", "Scaptius", "Matinius"],
    "brutus through scaptius and matinius": ["Brutus", "Scaptius", "Matinius"],
    "brutus or scaptius and matinius": ["Brutus", "Scaptius", "Matinius"],
    "terentia and tullia": ["Terentia", "Tullia"],
    "num. cloatius and m. cloatius": ["Num. Cloatius", "M. Cloatius"],
    "num. and m. cloatius": ["Num. Cloatius", "M. Cloatius"],
    "c. and m. fufius": ["C. Fufius", "M. Fufius"],
    "sex. stloga then c. and m. fufius": ["Sex. Stloga", "C. Fufius", "M. Fufius"],
    "rabirius postumus and his amici": ["Rabirius Postumus", "Rabirius Postumus amici"],
    "friends pledged lands and slaves to the public treasury": ["friends of Cato"],
    "salamis and ariobarzanes iii": ["Salamis", "Ariobarzanes III"],
    "l. octavius naso or heir flavius": ["L. Octavius Naso", "L. Flavius"],
    "l. carpinatius / sicilian tax company": ["L. Carpinatius", "Sicilian tax company"],
    "philocles and heraclea and bargylia and caunus": ["Philocles", "Heraclea", "Bargylia", "Caunus"],
    "antonius or octavius as governor/intermediary": ["C. Antonius Hybrida", "C. Octavius"],
    "pompey/cluvius as agent": ["Pompey", "Cluvius"],
}

COLLAPSE_LABELS = {
    "brutus as alleged surety": "Brutus",
    "brutus as patron/recommender": "Brutus",
    "crassus as surety": "Crassus",
    "d. iunius brutus as guarantor": "D. Iunius Brutus",
    "hermippus as surety": "Hermippus",
    "p. sulla as procurator": "P. Sulla",
    "pompey as prior arbiter": "Pompey",
    "sex. naevius as promised source of funds": "Sex. Naevius",
    "verres as bribe recipient": "Verres",
    "brutus / brutus' military command": "Brutus",
    "scapula estate or sellers": "Scapula estate",
    "children/heirs of scapula": "Scapula heirs",
}


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


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return f"actor_{cleaned}" if cleaned else ""


def join_sorted(values: set[str]) -> str:
    return "; ".join(sorted(value for value in values if value))


def join_counter(counter: Counter[str], limit: int = 8) -> str:
    return "; ".join(f"{key} ({value})" for key, value in counter.most_common(limit) if key)


def graph_names(name: str) -> list[str]:
    cleaned = name.strip()
    lowered = cleaned.lower()
    if not cleaned:
        return []
    if lowered in SPLIT_LABELS:
        return SPLIT_LABELS[lowered]
    if lowered in COLLAPSE_LABELS:
        return [COLLAPSE_LABELS[lowered]]
    return [cleaned]


def graph_transform(name: str) -> tuple[str, list[str], str]:
    cleaned = name.strip()
    lowered = cleaned.lower()
    if not cleaned:
        return "omit", [], "blank label"
    if lowered in SPLIT_LABELS:
        return "split", SPLIT_LABELS[lowered], "multiple identifiable actors or reviewed composite label"
    if lowered in COLLAPSE_LABELS:
        return "collapse", [COLLAPSE_LABELS[lowered]], "role-qualified single-person label collapsed to person node"
    if is_placeholder(cleaned):
        return "exclude_placeholder", [cleaned], "non-actor placeholder retained in node table but excluded from graph edges"
    return "keep", [cleaned], "label retained"


def is_placeholder(name: str) -> bool:
    lowered = name.lower()
    return lowered in SOURCE_AUTHOR_LABELS or any(re.search(pattern, lowered) for pattern in PLACEHOLDER_PATTERNS)


def is_collective(name: str) -> bool:
    lowered = name.lower()
    return any(re.search(pattern, lowered) for pattern in COLLECTIVE_PATTERNS)


def identity_base(name: str) -> str:
    lowered = name.lower()
    if any(term in lowered for term in ["mother-in-law", "creditors", "debtors", "amici"]):
        return name
    if "d. iunius brutus" in lowered:
        return "D. Iunius Brutus"
    if "brutus albinus" in lowered:
        return "Brutus Albinus"
    if "brutus through" in lowered or "brutus or scaptius" in lowered or "brutus as" in lowered:
        return "Brutus"
    if lowered in {"brvto", "bruto"}:
        return "Brutus"
    for marker in [" as ", " through ", " or ", " / ", "'s "]:
        if marker in lowered:
            pattern = re.compile(re.escape(marker), re.IGNORECASE)
            return pattern.split(name, maxsplit=1)[0].strip()
    return name


def identity_resolution(name: str, actor_type: str) -> tuple[str, str]:
    lowered = name.lower()
    base = identity_base(name)
    if actor_type == "uncertain_actor":
        return base, "composite_or_ambiguous_preserve_for_transaction_graph"
    if actor_type in {"civic_body", "public_body", "collective_group", "estate"}:
        return base, "entity_node"
    if " through " in lowered or " or " in lowered or "/" in name:
        return base, "composite_or_ambiguous_preserve_for_transaction_graph"
    if " as " in lowered:
        return base, "role_qualified_alias_review_before_merge"
    if base != name:
        return base, "alias_candidate_review_before_merge"
    return base, "canonical_identity"


def classify_actor(name: str) -> tuple[str, str, str, str]:
    lowered = name.lower()
    if is_placeholder(name):
        return "non_actor_placeholder", "placeholder", "unknown", "Role label retained for provenance only."
    civic_terms = {
        "arpinum",
        "athens",
        "asian cities",
        "buthrotum stakeholders",
        "byllis",
        "cities in asia",
        "city of byllis",
        "city of dyrrhachium",
        "city of gytheion",
        "city of sicyon",
        "city of tenos",
        "dyrrhachium",
        "gytheion",
        "nicaea",
        "salamis",
        "sardis",
        "sicyon",
        "tenos",
    }
    if lowered in civic_terms or lowered.startswith("city of ") or " cities" in lowered or lowered.startswith("cities in "):
        return "civic_body", "city_or_civic_community", "identified", ""
    if "provincial governor" in lowered:
        return "public_body", "public_office", "ambiguous", "Office label; preserve separately from any named office-holder."
    if "salamis and" in lowered:
        return "uncertain_actor", "civic_person_composite", "ambiguous", "Composite label combining a civic body with another actor; preserve until split by source review."
    if "heraclea" in lowered or "bargylia" in lowered or "caunus" in lowered:
        return "uncertain_actor", "person_civic_composite", "ambiguous", "Composite label combining personal and civic names; preserve until split by source review."
    if " through " in lowered or " or " in lowered or "/" in name:
        return "uncertain_actor", "composite_or_ambiguous_identity", "ambiguous", "Composite or role-qualified label; review before merging with a person node."
    if " as " in lowered:
        return "uncertain_actor", "role_qualified_identity", "ambiguous", "Role-qualified label; review before merging with a person node."
    if is_collective(name):
        if "publicani" in lowered or "tax company" in lowered:
            return "collective_group", "tax_company", "collective", ""
        if "communities" in lowered:
            return "civic_body", "provincial_community", "collective", ""
        if "creditor" in lowered:
            return "collective_group", "creditor_group", "collective", ""
        if "sponsores" in lowered or "procurators" in lowered:
            return "collective_group", "role_group", "collective", ""
        return "collective_group", "collective", "collective", ""
    if any(term in lowered for term in ["estate", "goods of", "bonorum"]):
        return "estate", "estate_or_property", "identified", ""
    if any(term in lowered for term in ["state", "senate", "public contract"]):
        return "public_body", "public_or_civic", "identified", ""
    if any(term in lowered for term in ["tiro", "eros", "philotimus", "philogenes", "statius"]):
        return "freedman_or_agent", "agent_or_account_manager", "identified", ""
    if any(term in lowered for term in ["terentia", "tullia", "quintus cicero", "cicero family"]):
        return "family_or_household", "family_or_household", "identified", ""
    if lowered in SECONDARY_FINANCE_ROLE_NOTES:
        return (
            "professional_financier",
            "finance_intermediary",
            "identified",
            SECONDARY_FINANCE_ROLE_NOTES[lowered],
        )
    if any(term in lowered for term in ["argentarius", "banker", "selicius"]):
        return "professional_financier", "banker_or_financier", "identified", ""
    return "individual", "individual", "identified", ""


def edge_layer(edge_type: str) -> str:
    return "direct_financial" if edge_type == "borrower_to_lender" else "third_party_context"


def edge_roles(edge_type: str) -> tuple[str, str]:
    if edge_type == "borrower_to_lender":
        return "borrower", "lender"
    if edge_type == "third_party_to_borrower_context":
        return "third_party", "borrower"
    if edge_type == "third_party_to_lender_context":
        return "third_party", "lender"
    return "source", "target"


def source_support_tier(canonical_row: dict[str, str]) -> str:
    text = " ".join(
        [
            canonical_row.get("verification_status", ""),
            canonical_row.get("primary_source_verified", ""),
            canonical_row.get("source_enrichment_note", ""),
        ]
    ).lower()
    if "followup" in text or "unavailable" in text or "manual_review" in text:
        return "follow-up needed"
    if "latin_controlled" in text or "latin_checked" in text:
        return "Latin-controlled"
    if "online_latin" in text or "translation_checked" in text or "primary" in text:
        return "primary-source checked"
    source_layer = canonical_row.get("source_layer")
    if "verboven_only" in text or source_layer in {"secondary_source_records", "verboven_expansion"}:
        return "Secondary-source record"
    if canonical_row.get("source_layer") == "canonical_core":
        return "Latin-controlled"
    return "Source-expansion record"


def amount_tier(analysis_row: dict[str, str], canonical_row: dict[str, str]) -> str:
    if analysis_row.get("normalized_amount_hs", "").strip():
        return "normalized"
    triage_text = " ".join(
        [
            analysis_row.get("amount", ""),
            analysis_row.get("currency_or_unit", ""),
            canonical_row.get("amount_note", ""),
        ]
    ).lower()
    if any(term in triage_text for term in ["descriptive", "talent", "under review", "uncertain", "multiple"]):
        return "descriptive"
    if analysis_row.get("amount_present") == "yes" or analysis_row.get("amount", "").strip():
        return "unknown"
    return "unknown"


def mechanism_type(row: dict[str, str]) -> str:
    text = " ".join(
        [
            row.get("analysis_loan_type", ""),
            row.get("loan_type", ""),
            row.get("status", ""),
            row.get("third_party_involvement_types", ""),
            row.get("third_party_involvement_summary", ""),
            row.get("interpretive_note", ""),
            row.get("latin_evidence", ""),
            row.get("english_evidence", ""),
        ]
    ).lower()
    if "versura" in text or "refinanc" in text:
        return "refinancing/versura"
    if "nomina" in text or "nomen" in text or "account" in text or "syngraph" in text or "permutation" in text:
        return "account/nomina"
    if "surety" in text or "guarantee" in text or "sponsor" in text or "satis" in text or "praediator" in text:
        return "surety"
    if "recommend" in text or "patron" in text or "fides" in text:
        return "recommendation"
    if "delegate" in text or "payer" in text or "payment intermediary" in text or "collection agent" in text:
        return "delegated payment"
    if "overdue" in text or "pressure" in text or "disputed" in text or "repayment" in text or "satisfy" in text:
        return "repayment pressure"
    if any(term in text for term in ["political", "public", "civic", "royal", "senate", "state", "provincial"]):
        return "political/civic finance"
    if "personal loan" in text or "mutu" in text or "loan" in text:
        return "direct loan"
    return "ambiguous"


def scope_type(analysis_row: dict[str, str], canonical_row: dict[str, str]) -> str:
    text = " ".join(
        [
            canonical_row.get("core_eligibility", ""),
            canonical_row.get("reason_not_core", ""),
            canonical_row.get("source_genre", ""),
            canonical_row.get("brief_description", ""),
            analysis_row.get("borrower", ""),
            analysis_row.get("lender", ""),
            analysis_row.get("third_parties", ""),
            analysis_row.get("interpretive_note", ""),
        ]
    ).lower()
    if canonical_row.get("source_genre") not in {"", "letter"}:
        return "comparative"
    if "out_of_scope_public" in text or "public" in text or "state" in text or "senate" in text:
        return "public"
    if "civic" in text or "city" in text or "communities" in text or "provincial" in text:
        return "civic"
    if "political" in text or "campaign" in text:
        return "political"
    if "royal" in text or "king" in text or "ptolemy" in text or "ariobarzanes" in text:
        return "royal"
    if "comparative" in text:
        return "comparative"
    if "household" in text or "terentia" in text or "tullia" in text or "tiro" in text:
        return "household"
    if canonical_row.get("core_eligibility", "") in {"context_only", "out_of_scope_non_letter"}:
        return "ambiguous"
    return "private"


def parse_date_bounds(date_text: str, fallback_year_bce: str) -> tuple[str, str, str, str]:
    """Return period, certainty, min_year, max_year with BCE negative and CE positive."""
    bracket_match = re.search(r"\[([^\]]+)\]", date_text or "")
    bracket = bracket_match.group(1).strip() if bracket_match else ""
    if bracket.lower() == "n.d.":
        return "undated", "undated", "", ""
    ce_match = re.search(r"(\d{1,4})(?:-(\d{1,4}))?\s*(?:CE|AD)", bracket, re.I)
    if ce_match:
        start = int(ce_match.group(1))
        end = int(ce_match.group(2) or ce_match.group(1))
        return "imperial_comparative", "range" if ce_match.group(2) else "exact", str(start), str(end)
    bce_match = re.search(r"(\d{1,4})(?:-(\d{1,4}))?\s*BCE", bracket, re.I)
    if bce_match:
        first = int(bce_match.group(1))
        second = int(bce_match.group(2) or bce_match.group(1))
        start = -max(first, second)
        end = -min(first, second)
        if end < -100:
            period = "pre_ciceronian_context"
        elif start > -40:
            period = "post_ciceronian_bce_comparative"
        elif start <= -40 and end >= -100:
            period = "ciceronian_period"
        else:
            period = "borderline_ciceronian_period"
        return period, "range" if bce_match.group(2) else "exact", str(start), str(end)
    if fallback_year_bce.strip().isdigit():
        value = -int(fallback_year_bce.strip())
        period = "ciceronian_period" if -100 <= value <= -40 else "pre_ciceronian_context"
        return period, "inferred_from_analysis_year", str(value), str(value)
    return "undated", "undated", "", ""


def build_record_lookup() -> dict[str, dict[str, str]]:
    analysis_rows = {row["record_id"]: row for row in load_rows(ANALYSIS_SOURCE)}
    canonical_rows = {}
    for row in load_rows(CANONICAL_SOURCE):
        rid = row.get("merged_record_id") or row.get("canonical_record_id") or row.get("representative_record_id")
        canonical_rows[rid] = row

    lookup: dict[str, dict[str, str]] = {}
    for record_id, analysis_row in analysis_rows.items():
        canonical_row = canonical_rows.get(record_id, {})
        period, date_certainty, date_min, date_max = parse_date_bounds(
            canonical_row.get("date", ""), analysis_row.get("year_bce", "")
        )
        lookup[record_id] = {
            **analysis_row,
            "canonical_loan_type": analysis_row.get("loan_type", ""),
            "source_layer": canonical_row.get("source_layer", ""),
            "source_genre": canonical_row.get("source_genre", ""),
            "verification_status": canonical_row.get("verification_status", ""),
            "primary_source_verified": canonical_row.get("primary_source_verified", ""),
            "core_eligibility": canonical_row.get("core_eligibility", ""),
            "source_support_tier": source_support_tier(canonical_row),
            "amount_tier": amount_tier(analysis_row, canonical_row),
            "mechanism_type": mechanism_type(analysis_row),
            "scope_type": scope_type(analysis_row, canonical_row),
            "date_period": period,
            "date_certainty": date_certainty,
            "date_min_year": date_min,
            "date_max_year": date_max,
        }
    return lookup


def build_node_stats(
    party_rows: list[dict[str, str]], edge_rows: list[dict[str, str]]
) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "records": set(),
            "direct_records": set(),
            "third_party_records": set(),
            "episodes": set(),
            "role_counts": Counter(),
            "weighted_degree": 0,
            "direct_edge_degree": 0,
            "context_edge_degree": 0,
            "confidences": set(),
        }
    )

    for row in party_rows:
        for name in graph_names(row["canonical_party"]):
            stats[name]["role_counts"].update([row["role_type"]])
            if row["is_direct_party"] == "yes":
                stats[name]["direct_records"].add(row["record_id"])
                stats[name]["records"].add(row["record_id"])
                stats[name]["episodes"].add(row["episode_group"])
                stats[name]["confidences"].add(row["confidence"])
            if row["is_third_party"] == "yes":
                stats[name]["third_party_records"].add(row["record_id"])
                stats[name]["records"].add(row["record_id"])
                stats[name]["episodes"].add(row["episode_group"])
                stats[name]["confidences"].add(row["confidence"])

    for row in edge_rows:
        sources = graph_names(row["source_canonical"])
        targets = graph_names(row["target_canonical"])
        direct = row["edge_type"] == "borrower_to_lender"
        for source in sources:
            for target in targets:
                if source == target:
                    continue
                for name in [source, target]:
                    stats[name]["weighted_degree"] = int(stats[name]["weighted_degree"]) + 1
                    if direct:
                        stats[name]["direct_edge_degree"] = int(stats[name]["direct_edge_degree"]) + 1
                    else:
                        stats[name]["context_edge_degree"] = int(stats[name]["context_edge_degree"]) + 1
                    stats[name]["records"].add(row["record_id"])
                    stats[name]["episodes"].add(row["episode_group"])
                    stats[name]["confidences"].add(row["confidence"])
    return stats


def build_nodes(stats: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, values in stats.items():
        actor_type, actor_subtype, certainty, note = classify_actor(name)
        base_name, resolution = identity_resolution(name, actor_type)
        placeholder = actor_type == "non_actor_placeholder"
        role_counts: Counter[str] = values["role_counts"]
        rows.append(
            {
                "node_id": slug(name),
                "canonical_name": name,
                "display_name": name,
                "identity_base_name": base_name,
                "identity_group": slug(base_name).replace("actor_", "identity_", 1),
                "identity_resolution": resolution,
                "actor_type": actor_type,
                "actor_subtype": actor_subtype,
                "certainty": certainty,
                "is_collective": "yes" if certainty == "collective" else "no",
                "is_placeholder": "yes" if placeholder else "no",
                "include_in_centrality": "no" if placeholder else "yes",
                "record_count": len(values["records"]),
                "direct_record_count": len(values["direct_records"]),
                "third_party_record_count": len(values["third_party_records"]),
                "episode_count": len(values["episodes"]),
                "borrower_count": role_counts["borrower"],
                "lender_count": role_counts["lender"],
                "third_party_count": role_counts["third_party"],
                "sender_count": role_counts["sender"],
                "recipient_count": role_counts["recipient"],
                "weighted_degree": values["weighted_degree"],
                "direct_edge_degree": values["direct_edge_degree"],
                "context_edge_degree": values["context_edge_degree"],
                "confidence_values": join_sorted(values["confidences"]),
                "episode_groups": join_sorted(values["episodes"]),
                "notes": note,
            }
        )
    return sorted(rows, key=lambda row: (-int(row["weighted_degree"]), row["canonical_name"]))


def build_edges(
    edge_rows: list[dict[str, str]], valid_names: set[str], record_lookup: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str, str, str, str, str], dict[str, object]] = defaultdict(
        lambda: {
            "weight": 0,
            "records": set(),
            "episodes": set(),
            "confidences": set(),
            "years": set(),
            "collections": set(),
            "source_genres": set(),
            "verification_statuses": set(),
            "date_periods": set(),
            "date_certainties": set(),
            "date_min_years": set(),
            "date_max_years": set(),
        }
    )
    for row in edge_rows:
        record = record_lookup.get(row["record_id"], {})
        canonical_loan_type = record.get("canonical_loan_type", "")
        analysis_loan_type = record.get("analysis_loan_type", row.get("role_detail", ""))
        mechanism = record.get("mechanism_type", "ambiguous")
        scope = record.get("scope_type", "ambiguous")
        amount = record.get("amount_tier", "unknown")
        support = record.get("source_support_tier", "")
        date_period = record.get("date_period", "")
        date_certainty = record.get("date_certainty", "")
        for source in graph_names(row["source_canonical"]):
            for target in graph_names(row["target_canonical"]):
                if source == target or source not in valid_names or target not in valid_names:
                    continue
                key = (
                    source,
                    target,
                    row["edge_type"],
                    canonical_loan_type,
                    analysis_loan_type,
                    mechanism,
                    scope,
                    amount,
                    support,
                )
                grouped[key]["weight"] = int(grouped[key]["weight"]) + 1
                grouped[key]["records"].add(row["record_id"])
                grouped[key]["episodes"].add(row["episode_group"])
                grouped[key]["confidences"].add(row["confidence"])
                grouped[key]["years"].add(row["year_bce"])
                grouped[key]["collections"].add(row["collection"])
                grouped[key]["source_genres"].add(record.get("source_genre", ""))
                grouped[key]["verification_statuses"].add(record.get("verification_status", ""))
                grouped[key]["date_periods"].add(date_period)
                grouped[key]["date_certainties"].add(date_certainty)
                grouped[key]["date_min_years"].add(record.get("date_min_year", ""))
                grouped[key]["date_max_years"].add(record.get("date_max_year", ""))

    rows: list[dict[str, object]] = []
    for (
        source,
        target,
        edge_type,
        canonical_loan_type,
        analysis_loan_type,
        mechanism,
        scope,
        amount,
        support,
    ), values in grouped.items():
        source_role, target_role = edge_roles(edge_type)
        rows.append(
            {
                "source_id": slug(source),
                "target_id": slug(target),
                "source_name": source,
                "target_name": target,
                "edge_type": edge_type,
                "layer": edge_layer(edge_type),
                "actor_role_source": source_role,
                "actor_role_target": target_role,
                "canonical_loan_type": canonical_loan_type,
                "analysis_loan_type": analysis_loan_type,
                "mechanism_type": mechanism,
                "scope_type": scope,
                "amount_tier": amount,
                "source_support_tier": support,
                "date_period": join_sorted(values["date_periods"]),
                "date_certainty": join_sorted(values["date_certainties"]),
                "date_min_year": join_sorted(values["date_min_years"]),
                "date_max_year": join_sorted(values["date_max_years"]),
                "weight": values["weight"],
                "record_count": len(values["records"]),
                "records": join_sorted(values["records"]),
                "episode_count": len(values["episodes"]),
                "episode_groups": join_sorted(values["episodes"]),
                "year_bce_values": join_sorted(values["years"]),
                "collection_values": join_sorted(values["collections"]),
                "source_genre_values": join_sorted(values["source_genres"]),
                "verification_status_values": join_sorted(values["verification_statuses"]),
                "confidence_values": join_sorted(values["confidences"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["weight"]), row["source_name"], row["target_name"], row["edge_type"]))


def build_alias_provenance(
    party_rows: list[dict[str, str]], edge_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"record_ids": set(), "source_fields": set(), "outputs": set(), "action": "", "reason": ""}
    )
    for row in party_rows:
        raw = row["canonical_party"].strip()
        action, outputs, reason = graph_transform(raw)
        if action == "keep" or not raw:
            continue
        grouped[raw]["action"] = action
        grouped[raw]["reason"] = reason
        grouped[raw]["record_ids"].add(row["record_id"])
        grouped[raw]["source_fields"].add(row["role_type"])
        grouped[raw]["outputs"].update(outputs)
    for row in edge_rows:
        for field in ["source_canonical", "target_canonical"]:
            raw = row[field].strip()
            action, outputs, reason = graph_transform(raw)
            if action == "keep" or not raw:
                continue
            grouped[raw]["action"] = action
            grouped[raw]["reason"] = reason
            grouped[raw]["record_ids"].add(row["record_id"])
            grouped[raw]["source_fields"].add(field)
            grouped[raw]["outputs"].update(outputs)
    rows = []
    for raw, values in grouped.items():
        rows.append(
            {
                "raw_label": raw,
                "action": values["action"],
                "output_nodes": join_sorted(values["outputs"]),
                "reason": values["reason"],
                "record_ids": join_sorted(values["record_ids"]),
                "source_fields": join_sorted(values["source_fields"]),
                "review_status": "implemented" if values["action"] in {"split", "collapse", "exclude_placeholder"} else "review",
                "review_note": "Generated by actor graph normalization rules.",
            }
        )
    return sorted(rows, key=lambda row: (row["action"], row["raw_label"]))


def build_bipartite_rows(
    party_rows: list[dict[str, str]],
    included_names: set[str],
    record_lookup: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in party_rows:
        record = record_lookup.get(row["record_id"], {})
        for name in graph_names(row["canonical_party"]):
            if name not in included_names:
                continue
            key = (row["record_id"], name, row["role_type"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "record_id": row["record_id"],
                    "node_id": slug(name),
                    "canonical_name": name,
                    "role_type": row["role_type"],
                    "role_detail": row["role_detail"],
                    "is_direct_party": row["is_direct_party"],
                    "is_third_party": row["is_third_party"],
                    "episode_group": row["episode_group"],
                    "year_bce": row["year_bce"],
                    "confidence": row["confidence"],
                    "canonical_loan_type": record.get("canonical_loan_type", ""),
                    "analysis_loan_type": record.get("analysis_loan_type", ""),
                    "mechanism_type": record.get("mechanism_type", ""),
                    "scope_type": record.get("scope_type", ""),
                    "amount_tier": record.get("amount_tier", ""),
                    "source_support_tier": record.get("source_support_tier", ""),
                    "date_period": record.get("date_period", ""),
                    "date_certainty": record.get("date_certainty", ""),
                }
            )
    return sorted(rows, key=lambda row: (row["record_id"], row["canonical_name"], row["role_type"]))


def build_episode_rows(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "records": set(),
            "edges": 0,
            "direct": 0,
            "context": 0,
            "actors": Counter(),
            "mechanisms": set(),
            "scopes": set(),
            "loan_types": set(),
            "confidences": set(),
            "amounts": set(),
            "support": set(),
            "years": set(),
            "date_periods": set(),
        }
    )
    for edge in edges:
        episodes = [value.strip() for value in str(edge["episode_groups"]).split(";") if value.strip()] or ["(blank)"]
        records = {value.strip() for value in str(edge["records"]).split(";") if value.strip()}
        for episode in episodes:
            values = grouped[episode]
            values["records"].update(records)
            values["edges"] = int(values["edges"]) + int(edge["weight"])
            if edge["layer"] == "direct_financial":
                values["direct"] = int(values["direct"]) + int(edge["weight"])
            else:
                values["context"] = int(values["context"]) + int(edge["weight"])
            values["actors"].update([str(edge["source_name"]), str(edge["target_name"])])
            values["mechanisms"].add(str(edge["mechanism_type"]))
            values["scopes"].add(str(edge["scope_type"]))
            values["loan_types"].add(str(edge["analysis_loan_type"]))
            values["confidences"].update(v.strip() for v in str(edge["confidence_values"]).split(";") if v.strip())
            values["amounts"].add(str(edge["amount_tier"]))
            values["support"].add(str(edge["source_support_tier"]))
            values["years"].update(v.strip() for v in str(edge["year_bce_values"]).split(";") if v.strip())
            values["date_periods"].update(v.strip() for v in str(edge["date_period"]).split(";") if v.strip())

    rows = []
    for episode, values in grouped.items():
        rows.append(
            {
                "episode_group": episode,
                "record_count": len(values["records"]),
                "edge_count": values["edges"],
                "direct_edge_count": values["direct"],
                "third_party_context_edge_count": values["context"],
                "actor_count": len(values["actors"]),
                "mechanism_types": join_sorted(values["mechanisms"]),
                "scope_types": join_sorted(values["scopes"]),
                "analysis_loan_types": join_sorted(values["loan_types"]),
                "confidence_values": join_sorted(values["confidences"]),
                "amount_tiers": join_sorted(values["amounts"]),
                "source_support_tiers": join_sorted(values["support"]),
                "year_bce_values": join_sorted(values["years"]),
                "date_periods": join_sorted(values["date_periods"]),
                "top_actors": join_counter(values["actors"]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["episode_group"]))


def components(edges: list[dict[str, object]]) -> list[set[str]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge["source_name"])
        target = str(edge["target_name"])
        neighbors[source].add(target)
        neighbors[target].add(source)
    seen: set[str] = set()
    parts: list[set[str]] = []
    for node in sorted(neighbors):
        if node in seen:
            continue
        group: set[str] = set()
        queue: deque[str] = deque([node])
        seen.add(node)
        while queue:
            current = queue.popleft()
            group.add(current)
            for nxt in sorted(neighbors[current]):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        parts.append(group)
    return sorted(parts, key=lambda item: (-len(item), sorted(item)))


def graph_neighbors(edges: list[dict[str, object]]) -> tuple[list[str], dict[str, set[str]], dict[str, dict[str, int]]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    weighted_out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nodes: set[str] = set()
    for edge in edges:
        source = str(edge["source_name"])
        target = str(edge["target_name"])
        weight = int(edge["weight"])
        nodes.update([source, target])
        neighbors[source].add(target)
        neighbors[target].add(source)
        weighted_out[source][target] += weight
    ordered = sorted(nodes)
    for node in ordered:
        neighbors[node]
        weighted_out[node]
    return ordered, neighbors, weighted_out


def pagerank(nodes: list[str], weighted_out: dict[str, dict[str, int]]) -> dict[str, float]:
    if not nodes:
        return {}
    damping = 0.85
    ranks = dict.fromkeys(nodes, 1.0 / len(nodes))
    out_weight = {node: sum(weighted_out[node].values()) for node in nodes}
    for _ in range(100):
        dangling = sum(ranks[node] for node in nodes if out_weight[node] == 0)
        next_ranks = dict.fromkeys(nodes, (1.0 - damping) / len(nodes) + damping * dangling / len(nodes))
        for source in nodes:
            if out_weight[source] == 0:
                continue
            for target, weight in weighted_out[source].items():
                next_ranks[target] += damping * ranks[source] * weight / out_weight[source]
        if sum(abs(next_ranks[node] - ranks[node]) for node in nodes) < 1.0e-12:
            ranks = next_ranks
            break
        ranks = next_ranks
    return ranks


def betweenness(nodes: list[str], neighbors: dict[str, set[str]]) -> dict[str, float]:
    scores = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {node: [] for node in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = dict.fromkeys(nodes, -1)
        distance[source] = 0
        queue: deque[str] = deque([source])
        while queue:
            current = queue.popleft()
            stack.append(current)
            for nxt in sorted(neighbors[current]):
                if distance[nxt] < 0:
                    queue.append(nxt)
                    distance[nxt] = distance[current] + 1
                if distance[nxt] == distance[current] + 1:
                    sigma[nxt] += sigma[current]
                    predecessors[nxt].append(current)
        dependency = dict.fromkeys(nodes, 0.0)
        while stack:
            node = stack.pop()
            for prev in predecessors[node]:
                if sigma[node]:
                    dependency[prev] += (sigma[prev] / sigma[node]) * (1.0 + dependency[node])
            if node != source:
                scores[node] += dependency[node]
    if len(nodes) > 2:
        scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
        for node in nodes:
            scores[node] *= scale
    return scores


def build_variant_centrality(variant_edges: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for variant_name, edges in variant_edges.items():
        nodes, neighbors, weighted_out = graph_neighbors(edges)
        ranks = pagerank(nodes, weighted_out)
        between = betweenness(nodes, neighbors)
        comps = components(edges)
        component_size = {}
        for comp in comps:
            for node in comp:
                component_size[node] = len(comp)
        weighted_degree = Counter()
        for edge in edges:
            weighted_degree.update({str(edge["source_name"]): int(edge["weight"])})
            weighted_degree.update({str(edge["target_name"]): int(edge["weight"])})
        ordered = sorted(
            nodes,
            key=lambda node: (-ranks.get(node, 0.0), -between.get(node, 0.0), -weighted_degree[node], node),
        )
        for index, node in enumerate(ordered, start=1):
            rows.append(
                {
                    "variant_name": variant_name,
                    "centrality_rank": index,
                    "canonical_name": node,
                    "weighted_degree": weighted_degree[node],
                    "component_size": component_size.get(node, 0),
                    "pagerank": f"{ranks.get(node, 0.0):.6f}",
                    "betweenness": f"{between.get(node, 0.0):.6f}",
                }
            )
    return rows


def variant_summary(name: str, description: str, edges: list[dict[str, object]], recipe: str) -> dict[str, object]:
    node_counts = Counter()
    records: set[str] = set()
    for edge in edges:
        node_counts.update([str(edge["source_name"]), str(edge["target_name"])])
        records.update(v.strip() for v in str(edge["records"]).split(";") if v.strip())
    comps = components(edges)
    output_path = VARIANTS / f"{name}.csv"
    return {
        "variant_name": name,
        "description": description,
        "output_path": str(output_path.relative_to(ROOT)),
        "node_count": len(node_counts),
        "edge_count": len(edges),
        "record_count": len(records),
        "component_count": len(comps),
        "largest_component_node_count": len(comps[0]) if comps else 0,
        "top_weighted_degree_nodes": join_counter(node_counts),
        "filter_recipe": recipe,
    }


def build_variants(edges: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    variants = {
        "combined_transaction_graph": (
            "All included transaction-safe actor edges.",
            edges,
            "all actor_edges rows",
        ),
        "direct_borrower_lender_graph": (
            "Direct borrower-lender edges only.",
            [e for e in edges if e["layer"] == "direct_financial"],
            "layer == direct_financial",
        ),
        "third_party_context_graph": (
            "Third-party context edges only.",
            [e for e in edges if e["layer"] == "third_party_context"],
            "layer == third_party_context",
        ),
        "cicero_removed_graph": (
            "All edges with Cicero removed.",
            [e for e in edges if e["source_name"] != "Cicero" and e["target_name"] != "Cicero"],
            "source_name != Cicero and target_name != Cicero",
        ),
        "core_only_graph": (
            "Edges from Latin-controlled/core source support.",
            [e for e in edges if e["source_support_tier"] == "Latin-controlled"],
            "source_support_tier == Latin-controlled",
        ),
        "expanded_graph": (
            "Edges from the full expanded analysis layer.",
            edges,
            "all actor_edges rows; includes core and expansion rows",
        ),
        "high_confidence_graph": (
            "Edges with high confidence only.",
            [e for e in edges if set(str(e["confidence_values"]).split("; ")) == {"high"}],
            "confidence_values == high",
        ),
        "letters_only_graph": (
            "Edges from letter source genre only.",
            [e for e in edges if set(str(e["source_genre_values"]).split("; ")) <= {"letter", ""}],
            "source_genre_values only letter or blank",
        ),
        "episode_level_graph": (
            "Record-level edges retained with episode metadata for episode aggregation.",
            edges,
            "use episode_nodes.csv for collapsed episode interpretation",
        ),
        "ciceronian_period_graph": (
            "Edges dated to the main Cicero-era analytical window, 100-40 BCE.",
            [e for e in edges if e["date_period"] == "ciceronian_period"],
            "date_period == ciceronian_period",
        ),
        "ciceronian_period_cicero_removed_graph": (
            "Ciceronian-period edges with Cicero removed.",
            [
                e
                for e in edges
                if e["date_period"] == "ciceronian_period"
                and e["source_name"] != "Cicero"
                and e["target_name"] != "Cicero"
            ],
            "date_period == ciceronian_period; source_name != Cicero and target_name != Cicero",
        ),
        "comparative_or_undated_graph": (
            "Edges outside the 100-40 BCE window or without usable event dates.",
            [e for e in edges if e["date_period"] != "ciceronian_period"],
            "date_period != ciceronian_period",
        ),
        "monetary_subgraph": (
            "High-confidence source-controlled normalized amount edges.",
            [
                e
                for e in edges
                if e["amount_tier"] == "normalized"
                and e["date_period"] == "ciceronian_period"
                and e["source_support_tier"] in {"Latin-controlled", "primary-source checked"}
                and set(str(e["confidence_values"]).split("; ")) <= {"high"}
                and e["scope_type"] in {"private", "household"}
            ],
            "amount_tier == normalized; date_period == ciceronian_period; source_support_tier in Latin-controlled/primary-source checked; high confidence; private/household scope",
        ),
    }
    manifest = []
    for name, (description, variant_edges, recipe) in variants.items():
        manifest.append(variant_summary(name, description, variant_edges, recipe))
    return manifest, {name: data[1] for name, data in variants.items()}


def build_actor_type_summary(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"nodes": 0, "weighted": 0, "direct": 0, "context": 0, "records": set(), "top": Counter()}
    )
    for node in nodes:
        if node["include_in_centrality"] != "yes":
            continue
        key = str(node["actor_type"])
        grouped[key]["nodes"] = int(grouped[key]["nodes"]) + 1
        grouped[key]["weighted"] = int(grouped[key]["weighted"]) + int(node["weighted_degree"])
        grouped[key]["direct"] = int(grouped[key]["direct"]) + int(node["direct_edge_degree"])
        grouped[key]["context"] = int(grouped[key]["context"]) + int(node["context_edge_degree"])
        grouped[key]["top"].update({str(node["canonical_name"]): int(node["weighted_degree"])})
        # record_count is already unique per node; use a synthetic count total for type-level scan.
        grouped[key]["records"].add(str(node["canonical_name"]))
    rows = []
    for actor_type, values in grouped.items():
        rows.append(
            {
                "actor_type": actor_type,
                "node_count": values["nodes"],
                "weighted_degree": values["weighted"],
                "direct_edge_degree": values["direct"],
                "context_edge_degree": values["context"],
                "record_count": "",
                "top_nodes": join_counter(values["top"], 10),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["weighted_degree"]), row["actor_type"]))


def build_mechanism_summary(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {"edges": 0, "direct": 0, "context": 0, "actors": Counter(), "records": set()}
    )
    for edge in edges:
        key = (str(edge["analysis_loan_type"]), str(edge["mechanism_type"]), str(edge["scope_type"]))
        grouped[key]["edges"] = int(grouped[key]["edges"]) + int(edge["weight"])
        if edge["layer"] == "direct_financial":
            grouped[key]["direct"] = int(grouped[key]["direct"]) + int(edge["weight"])
        else:
            grouped[key]["context"] = int(grouped[key]["context"]) + int(edge["weight"])
        grouped[key]["actors"].update({str(edge["source_name"]): int(edge["weight"])})
        grouped[key]["actors"].update({str(edge["target_name"]): int(edge["weight"])})
        grouped[key]["records"].update(v.strip() for v in str(edge["records"]).split(";") if v.strip())
    rows = []
    for (loan_type, mechanism, scope), values in grouped.items():
        rows.append(
            {
                "analysis_loan_type": loan_type,
                "mechanism_type": mechanism,
                "scope_type": scope,
                "edge_count": values["edges"],
                "direct_edge_count": values["direct"],
                "third_party_context_edge_count": values["context"],
                "actor_count": len(values["actors"]),
                "record_count": len(values["records"]),
                "top_actors": join_counter(values["actors"], 8),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["edge_count"]), row["analysis_loan_type"], row["mechanism_type"]))


def quality_row(
    name: str, severity: str, count: int, examples: list[str], recommendation: str
) -> dict[str, object]:
    return {
        "check_name": name,
        "severity": severity,
        "status": "pass" if count == 0 else "review",
        "count": count,
        "examples": "; ".join(examples[:12]),
        "recommendation": recommendation,
    }


def build_quality_report(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> list[dict[str, object]]:
    node_by_name = {str(row["canonical_name"]): row for row in nodes}
    rows: list[dict[str, object]] = []
    placeholder_edges = [
        f"{edge['source_name']}->{edge['target_name']}"
        for edge in edges
        if node_by_name.get(str(edge["source_name"]), {}).get("is_placeholder") == "yes"
        or node_by_name.get(str(edge["target_name"]), {}).get("is_placeholder") == "yes"
    ]
    rows.append(
        quality_row(
            "placeholder_nodes_in_edges",
            "error",
            len(placeholder_edges),
            placeholder_edges,
            "Exclude non-actor placeholders from actor_edges.csv.",
        )
    )
    city_individuals = [
        str(node["canonical_name"])
        for node in nodes
        if node["actor_type"] == "individual"
        and re.search(r"\bcity\b|\bcities\b|athens|salamis|sardis|gytheion|tenos|dyrrhachium|sicyon", str(node["canonical_name"]).lower())
    ]
    rows.append(
        quality_row(
            "cities_classified_as_individuals",
            "error",
            len(city_individuals),
            city_individuals,
            "Classify cities and civic communities as civic_body.",
        )
    )
    source_authors = [
        str(node["canonical_name"])
        for node in nodes
        if str(node["canonical_name"]).lower() in SOURCE_AUTHOR_LABELS and node["include_in_centrality"] == "yes"
    ]
    rows.append(
        quality_row(
            "source_authors_classified_as_actors",
            "error",
            len(source_authors),
            source_authors,
            "Keep source-author labels provenance-only.",
        )
    )
    self_loops = [f"{edge['source_name']}->{edge['target_name']}" for edge in edges if edge["source_name"] == edge["target_name"]]
    rows.append(quality_row("self_loops_after_normalization", "warning", len(self_loops), self_loops, "Review split/collapse rules."))
    composite_nodes = [
        str(node["canonical_name"])
        for node in nodes
        if node["include_in_centrality"] == "yes"
        and re.search(r"\bor\b| through |/| and | as ", str(node["canonical_name"]).lower())
    ]
    rows.append(
        quality_row(
            "composite_labels_remaining",
            "warning",
            len(composite_nodes),
            composite_nodes,
            "Review whether remaining composites should be split, collapsed, or preserved.",
        )
    )
    missing_required = []
    for edge in edges:
        for field in ["records", "episode_groups", "confidence_values", "source_support_tier", "mechanism_type"]:
            if not str(edge.get(field, "")).strip():
                missing_required.append(f"{edge['source_name']}->{edge['target_name']} missing {field}")
                break
    rows.append(
        quality_row(
            "edges_missing_required_analysis_fields",
            "error",
            len(missing_required),
            missing_required,
            "Populate record, episode, confidence, source tier, and mechanism fields on every edge.",
        )
    )
    high_degree_uncertain = [
        f"{node['canonical_name']} ({node['weighted_degree']})"
        for node in nodes
        if node["include_in_centrality"] == "yes"
        and int(node["weighted_degree"]) >= 5
        and (node["actor_type"] == "uncertain_actor" or "low" in str(node["confidence_values"]))
    ]
    rows.append(
        quality_row(
            "high_degree_low_confidence_or_uncertain_nodes",
            "warning",
            len(high_degree_uncertain),
            high_degree_uncertain,
            "Review before using in prose centrality claims.",
        )
    )
    monetary_missing = [
        f"{edge['source_name']}->{edge['target_name']}"
        for edge in edges
        if edge["amount_tier"] == "normalized" and not edge["amount_tier"]
    ]
    rows.append(
        quality_row(
            "monetary_edges_lacking_amount_tier",
            "error",
            len(monetary_missing),
            monetary_missing,
            "Ensure monetary subgraph edges carry amount_tier.",
        )
    )
    outside_period = [
        f"{edge['records']}: {edge['date_period']}"
        for edge in edges
        if edge["date_period"] != "ciceronian_period"
    ]
    rows.append(
        quality_row(
            "edges_outside_ciceronian_period",
            "warning",
            len(outside_period),
            outside_period,
            "Use ciceronian_period_graph for 100-40 BCE analysis; reserve comparative_or_undated_graph for extrapolation/context.",
        )
    )
    undated_edges = [
        f"{edge['records']}: {edge['source_name']}->{edge['target_name']}"
        for edge in edges
        if "undated" in str(edge["date_period"])
    ]
    rows.append(
        quality_row(
            "undated_edges",
            "warning",
            len(undated_edges),
            undated_edges,
            "Do not use undated edges in chronology-sensitive claims without source review.",
        )
    )
    return rows


def build_positions(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> dict[str, tuple[float, float]]:
    visible = [node for node in nodes if node["include_in_centrality"] == "yes" and int(node["weighted_degree"]) > 0]
    top = visible[:44]
    remaining = visible[44:]
    width, height = 1280, 920
    cx, cy = width / 2, height / 2 + 15
    positions: dict[str, tuple[float, float]] = {}

    top_weight = max(int(node["weighted_degree"]) for node in top) if top else 1
    for index, node in enumerate(top):
        angle = 2 * math.pi * index / max(len(top), 1) - math.pi / 2
        weight = int(node["weighted_degree"])
        radius = 110 + (1 - weight / top_weight) * 270
        positions[str(node["node_id"])] = (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

    for index, node in enumerate(remaining[:80]):
        angle = 2 * math.pi * index / max(min(len(remaining), 80), 1) - math.pi / 2
        positions[str(node["node_id"])] = (cx + math.cos(angle) * 420, cy + math.sin(angle) * 420)

    return positions


def svg_node_color(actor_type: str) -> str:
    return {
        "individual": "#3f67a6",
        "family_or_household": "#9c5c9d",
        "freedman_or_agent": "#2f8f7f",
        "professional_financier": "#b56b36",
        "civic_body": "#69823a",
        "public_body": "#7a7f8c",
        "estate": "#86634a",
        "collective_group": "#687a9f",
        "uncertain_actor": "#8a8a8a",
    }.get(actor_type, "#8a8a8a")


def build_svg(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> str:
    node_by_id = {str(node["node_id"]): node for node in nodes}
    positions = build_positions(nodes, edges)
    visible_ids = set(positions)
    edge_lines = []
    for edge in edges:
        if edge["source_id"] not in visible_ids or edge["target_id"] not in visible_ids:
            continue
        x1, y1 = positions[str(edge["source_id"])]
        x2, y2 = positions[str(edge["target_id"])]
        direct = edge["layer"] == "direct_financial"
        stroke = "#b6423c" if direct else "#6f8fb3"
        width = 0.7 + math.sqrt(int(edge["weight"])) * (0.75 if direct else 0.45)
        opacity = "0.72" if direct else "0.32"
        edge_lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width:.2f}" stroke-opacity="{opacity}" />'
        )

    node_marks = []
    labels = []
    max_degree = max((int(node["weighted_degree"]) for node in nodes), default=1)
    for node_id, (x, y) in positions.items():
        node = node_by_id[node_id]
        degree = int(node["weighted_degree"])
        radius = 5 + math.sqrt(degree / max_degree) * 18
        color = svg_node_color(str(node["actor_type"]))
        node_marks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" '
            f'fill-opacity="0.92" stroke="#ffffff" stroke-width="1.5">'
            f'<title>{escape(str(node["display_name"]))}: {degree} edge attestations</title></circle>'
        )
        if degree >= 5 or str(node["canonical_name"]) in {"Cicero", "Atticus", "Quintus Cicero", "Caesar"}:
            anchor = "start" if x < 640 else "end"
            dx = radius + 4 if anchor == "start" else -radius - 4
            labels.append(
                f'<text x="{x + dx:.1f}" y="{y + 4:.1f}" text-anchor="{anchor}" '
                f'class="node-label">{escape(str(node["display_name"]))}</text>'
            )

    legend_items = [
        ("#b6423c", "direct borrower-lender edge"),
        ("#6f8fb3", "third-party context edge"),
        ("#3f67a6", "individual"),
        ("#2f8f7f", "freedman/agent"),
        ("#9c5c9d", "family/household"),
        ("#687a9f", "collective"),
    ]
    legend = []
    for i, (color, label) in enumerate(legend_items):
        y = 802 + i * 20
        if "edge" in label:
            legend.append(f'<line x1="36" y1="{y}" x2="58" y2="{y}" stroke="{color}" stroke-width="3" />')
        else:
            legend.append(f'<circle cx="47" cy="{y}" r="6" fill="{color}" />')
        legend.append(f'<text x="68" y="{y + 4}" class="legend-label">{escape(label)}</text>')

    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="920" viewBox="0 0 1280 920" role="img" aria-labelledby="title desc">',
            "<title id=\"title\">Cicero Loan Actor Graph</title>",
            "<desc id=\"desc\">Curated actor graph with direct financial and third-party context layers.</desc>",
            "<style>",
            "svg { background: #fbfaf7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }",
            ".title { font-size: 24px; font-weight: 700; fill: #252525; }",
            ".subtitle { font-size: 13px; fill: #555; }",
            ".node-label { font-size: 11px; font-weight: 600; fill: #252525; paint-order: stroke; stroke: #fbfaf7; stroke-width: 3px; }",
            ".legend-label { font-size: 12px; fill: #333; }",
            "</style>",
            '<text x="36" y="42" class="title">Cicero Loan Actor Graph</text>',
            '<text x="36" y="65" class="subtitle">Filtered actor nodes; red = direct borrower-lender, blue = third-party context. Node size = edge attestations.</text>',
            '<g class="edges">',
            *edge_lines,
            "</g>",
            '<g class="nodes">',
            *node_marks,
            "</g>",
            '<g class="labels">',
            *labels,
            "</g>",
            '<g class="legend">',
            *legend,
            "</g>",
            "</svg>",
        ]
    )


def write_summary(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> None:
    included = [node for node in nodes if node["include_in_centrality"] == "yes"]
    placeholders = [node for node in nodes if node["include_in_centrality"] == "no"]
    direct_edges = [edge for edge in edges if edge["layer"] == "direct_financial"]
    context_edges = [edge for edge in edges if edge["layer"] == "third_party_context"]
    mechanisms = Counter(str(edge["mechanism_type"]) for edge in edges)
    scopes = Counter(str(edge["scope_type"]) for edge in edges)
    amount_tiers = Counter(str(edge["amount_tier"]) for edge in edges)
    date_periods = Counter(str(edge["date_period"]) for edge in edges)
    top_nodes = sorted(included, key=lambda row: (-int(row["weighted_degree"]), str(row["canonical_name"])))[:12]
    lines = [
        "# Actor Graph Build",
        "",
        "Generated by `scripts/analysis/build_actor_graph.py`.",
        "",
        "## Outputs",
        "",
        "- `tables/actor_nodes.csv`: curated node authority table with actor types and role counts.",
        "- `tables/actor_edges.csv`: filtered weighted edge list split into direct and context layers.",
        "- `figures/cicero_actor_graph.svg`: static SVG graph for inspection and publication drafts.",
        "- `tables/graph_variant_centrality.csv`: PageRank, betweenness, weighted degree, and component size by graph variant.",
        "",
        "## Counts",
        "",
        f"- Included actor nodes: {len(included)}.",
        f"- Placeholder/provenance-only nodes: {len(placeholders)}.",
        f"- Weighted actor edges: {len(edges)}.",
        f"- Direct borrower-lender weighted edges: {len(direct_edges)}.",
        f"- Third-party context weighted edges: {len(context_edges)}.",
        f"- Mechanism types: {join_counter(mechanisms)}.",
        f"- Scope types: {join_counter(scopes)}.",
        f"- Amount tiers: {join_counter(amount_tiers)}.",
        f"- Date periods: {join_counter(date_periods)}.",
        "",
        "## Top Included Nodes By Edge Attestation",
        "",
    ]
    for node in top_nodes:
        lines.append(
            f"- {node['canonical_name']}: {node['weighted_degree']} edges; "
            f"{node['actor_type']}; {node['record_count']} records."
        )
    lines.extend(
        [
            "",
            "## Reading Rules",
            "",
            "- Use `direct_financial` for explicit borrower-lender relationships.",
            "- Use `third_party_context` for agents, managers, sureties, family actors, and account handlers.",
            "- Do not read edge weight as money volume; amount normalization remains incomplete.",
            "- Placeholder nodes are retained in the node table but excluded from the rendered graph.",
            "- Use `graph_variant_manifest.csv` for fixed Section 11 filter recipes.",
            "- Use `graph_quality_report.csv` before relying on centrality or monetary claims.",
            "- Use `ciceronian_period_graph` for 100-40 BCE analysis and `comparative_or_undated_graph` for later, earlier, or undated context.",
        ]
    )
    (GRAPH_ROOT / "actor_graph_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    record_lookup = build_record_lookup()
    party_rows = load_rows(PARTY_SOURCE)
    edge_rows = load_rows(EDGE_SOURCE)
    stats = build_node_stats(party_rows, edge_rows)
    nodes = build_nodes(stats)
    included_names = {str(row["canonical_name"]) for row in nodes if row["include_in_centrality"] == "yes"}
    edges = build_edges(edge_rows, included_names, record_lookup)
    alias_rows = build_alias_provenance(party_rows, edge_rows)
    bipartite_rows = build_bipartite_rows(party_rows, included_names, record_lookup)
    episode_rows = build_episode_rows(edges)
    quality_rows = build_quality_report(nodes, edges)
    variant_manifest, variant_edges = build_variants(edges)
    variant_centrality = build_variant_centrality(variant_edges)
    actor_type_summary = build_actor_type_summary(nodes)
    mechanism_summary = build_mechanism_summary(edges)

    write_rows(TABLES / "actor_nodes.csv", NODE_FIELDS, nodes)
    write_rows(TABLES / "actor_edges.csv", EDGE_FIELDS, edges)
    write_rows(TABLES / "actor_alias_provenance.csv", ALIAS_FIELDS, alias_rows)
    write_rows(TABLES / "episode_nodes.csv", EPISODE_FIELDS, episode_rows)
    write_rows(TABLES / "record_party_bipartite.csv", BIPARTITE_FIELDS, bipartite_rows)
    write_rows(TABLES / "graph_quality_report.csv", QUALITY_FIELDS, quality_rows)
    write_rows(TABLES / "graph_variant_manifest.csv", VARIANT_FIELDS, variant_manifest)
    write_rows(TABLES / "graph_variant_centrality.csv", VARIANT_CENTRALITY_FIELDS, variant_centrality)
    write_rows(TABLES / "actor_type_summary.csv", ACTOR_TYPE_SUMMARY_FIELDS, actor_type_summary)
    write_rows(TABLES / "mechanism_scope_summary.csv", MECHANISM_SUMMARY_FIELDS, mechanism_summary)
    for variant_name, rows in variant_edges.items():
        write_rows(VARIANTS / f"{variant_name}.csv", EDGE_FIELDS, rows)
    FIGURES.mkdir(parents=True, exist_ok=True)
    (FIGURES / "cicero_actor_graph.svg").write_text(build_svg(nodes, edges), encoding="utf-8")
    write_summary(nodes, edges)


if __name__ == "__main__":
    main()
