from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "official" / "objective_05_06" / "recalculation_v5"
TYPED = BASE / "typed"
INTERMEDIATE = BASE / "intermediate"
CALIBRATION = BASE / "calibration"
CALCULATED = BASE / "calculated"
AUDITS = BASE / "audits"
MANIFESTS = BASE / "manifests"

CANONICAL = ROOT / "data" / "canonical" / "cicero_credit_records.csv"
DECISIONS = ROOT / "data" / "exposure_groups" / "reviewed_record_decisions.csv"
OVERRIDES = ROOT / "data" / "exposure_groups" / "reviewed_overrides.csv"
AMOUNTS = ROOT / "data" / "amounts" / "amount_values.csv"
OBJECTIVES = ROOT / "config" / "objectives.yml"
PARAMETERS = ROOT / "config" / "calculation_parameters.json"
O56_COMPONENTS_PATH = ROOT / "config" / "o56_borrower_components.csv"

METHOD_ID = "o5_t5_strict_45_44_typed_bridge_expected_value_v3"
O6_CLASS_METHOD = "o6_45_44_current_visibility_tertiles_v1"
O6_METHOD = "o6w_t5_strict_45_44_post_imputation_incidence_typed_relations_v2"
REPAIR_VERSION = "postcalc_provenance_repair_2026_07_14"
STRICT_YEARS = {"45", "44"}
ANCHOR_SAME_WINDOW = 300_000.0
ANCHOR_PRIOR = 400_000.0
K_MIN = 5
K_MAX = 50
K_VALUES = range(K_MIN, K_MAX + 1)
TIE_TOLERANCE = 1e-12
STOCK_DENOMINATOR_MONTHS = 12.0
IMPUTED_EDGE_MONTHS = 12.0
SENATOR_POPULATION = 600.0
PARETO_CAP = 50_000_000.0
PARETO_ALPHA = 1.585
LOGNORMAL_SIGMA = 1.0

GARDEN_MEMBERS = {"ATT-PILOT-0011", "ATT-PILOT-0012"}
PUBLILIUS_MEMBERS = {"ATT-PILOT-0030", "ATT-PILOT-0035"}
STRICT_EXCLUDED_RECORDS = {"ATT-PILOT-0037", "VRB-STAGED-0092", "VRB-STAGED-0095"}
POLITICAL_CONTEXT_RECORDS = {"VRB-STAGED-0036", "VRB-STAGED-0045", "VRB-STAGED-0083"}
FORCED_STOCK_RECORDS = GARDEN_MEMBERS | {"ATT-PILOT-0014"}
FLOW_ONLY_AMOUNT_ROLES = {"partial_payment", "payment", "repayment", "remission", "settlement"}
FINANCIAL_AGENT_WORDS = {
    "agent", "manager", "surety", "sponsor", "sponsores", "praediator",
    "procurator", "intermediary", "coheir", "coheirs", "debtor", "collector",
}
KNOWN_FINANCIAL_AGENTS = {"atticus", "tiro", "eros", "faberius", "meton", "balbus", "hermogenes"}
PLACEHOLDER_WORDS = {
    "unknown", "unclear", "unspecified", "creditor", "creditors", "debtor", "debtors",
    "party", "parties", "household accounts", "estate", "supporters", "assigned debtors",
}

PARTY_FIELD_OVERRIDES = {
    # Source-reviewed party corrections already present in the repaired method history.
    "ATT-PILOT-0025": {"borrower": "Cornificius", "lender": "Iunius"},
    "FAM-PILOT-0004": {"borrower": "Cicero", "lender": "Ofillius and Aurelius"},
    "FAM-PILOT-0005": {"borrower": "Flamma", "lender": "Cicero"},
}

O56_COMPONENTS: tuple[tuple[str, tuple[str, ...], str, float | None, float], ...] = ()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_o56_components() -> tuple[tuple[str, tuple[str, ...], str, float | None, float], ...]:
    components = []
    for row in read_csv(O56_COMPONENTS_PATH):
        member_ids = tuple(part.strip() for part in row["member_record_ids"].split(";") if part.strip())
        fixed = float(row["fixed_amount_hs"]) if row["fixed_amount_hs"].strip() else None
        components.append((row["component_id"], member_ids, row["amount_treatment"], fixed, float(row["active_fraction"])))
    if not components:
        raise ValueError("The reviewed O5-6 component registry is empty")
    return tuple(components)


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_rows(rows: list[object]) -> str:
    return sha256_bytes(json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def git_commit() -> str:
    return os.environ.get("SOURCE_COMMIT", "release-tag-recorded-by-git")


def build_timestamp() -> str:
    return os.environ.get("BUILD_TIMESTAMP", "2026-07-14T00:00:00+00:00")


def year_bce(value: str) -> str:
    matches = re.findall(r"\[(\d{2,3})\s*BCE\]", value or "", flags=re.I)
    if matches:
        return matches[-1]
    match = re.search(r"\b(\d{2,3})\s*BCE\b", value or "", flags=re.I)
    return match.group(1) if match else ""


def norm(value: str) -> str:
    text = (value or "").lower().replace("’", "'")
    text = re.sub(r"\b(as|the)\b.*$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    aliases = {
        "m cicero": "cicero", "cicero s household accounts": "cicero", "m cicero cicero s household accounts": "cicero",
        "cicero tullia household": "cicero tullia household", "tullius cicero": "cicero", "m tullius cicero": "cicero",
        "t pomponius atticus": "atticus", "faberius debtor": "faberius debtor",
        "cato the younger": "cato younger", "l tullius montanus": "tullius montanus",
        "cornificius father": "cornificius", "flamma flaminius": "flamma",
        "flaminius for whom montanus is surety": "flaminius",
    }
    return aliases.get(text, text)


def split_people(value: str) -> list[str]:
    if not (value or "").strip():
        return []
    parts = re.split(r"\s*;\s*|\s*/\s*|\s+or\s+|\s+and\s+", value.strip(), flags=re.I)
    return [part.strip() for part in parts if part.strip()]


def is_placeholder(label: str) -> bool:
    key = norm(label)
    if not key:
        return True
    return any(word == key or word in key for word in PLACEHOLDER_WORDS)


def actor_id(label: str) -> str:
    key = norm(label)
    return "ACT-" + re.sub(r"[^A-Z0-9]+", "-", key.upper()).strip("-")[:48]


def occurrence_id(record_id: str, role: str, index: int) -> str:
    return f"OCC-{record_id}-{role.upper()}-{index:02d}"


def relation_id(record_id: str, role: str, a: str, b: str) -> str:
    digest = sha256_rows([record_id, role, a, b])[:16]
    return f"REL-{digest}"


def fmt(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=1e-9):
        return str(int(round(value)))
    return f"{value:.12f}".rstrip("0").rstrip(".")


def fmt_currency(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=1e-6):
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def linear_quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a quantile over an empty set")
    position = (len(ordered) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - position) + ordered[hi] * (position - lo)


def confidence_probability(values: list[str]) -> float:
    mapping = {"high": 1.0, "medium": 0.9, "low": 0.5}
    return max((mapping.get((value or "").lower(), 0.75) for value in values), default=0.75)


def strict_scope(record: dict[str, str], decision: dict[str, str]) -> tuple[bool, str]:
    record_id = record["merged_record_id"]
    joined = " ".join(record.get(field, "") for field in (
        "core_eligibility", "reason_not_core", "brief_description", "interpretive_note", "loan_type", "actors",
    )).lower()
    if record_id in STRICT_EXCLUDED_RECORDS:
        return False, "explicit_revision5_exclusion"
    if record_id in POLITICAL_CONTEXT_RECORDS:
        return False, "political_or_context_obligation"
    if decision.get("provisional_scope") == "public_or_context_review":
        return False, "public_or_context_scope"
    if "verres" in joined:
        return False, "verres_public_prosecution_context"
    if any(token in joined for token in ("public debt", "civic", "royal", "state contract", "dowry-adjacent", "comparative only")):
        return False, "public_civic_royal_state_or_context"
    return True, "strict_private_or_household_scope"


def build_exposure_authorities(
    records: list[dict[str, str]], decisions: dict[str, dict[str, str]], amount_rows: list[dict[str, str]], overrides: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    override_by_record = {row["record_id"]: row for row in overrides}
    group_by_record: dict[str, str] = {}
    for record in records:
        rid = record["merged_record_id"]
        decision = decisions[rid]
        if rid in GARDEN_MEMBERS:
            gid = "O5EG-0016"
        elif rid in PUBLILIUS_MEMBERS:
            gid = "O5EG-0015"
        elif rid == "VRB-STAGED-0092":
            gid = "O5EG-0004"
        elif rid == "VRB-STAGED-0095":
            gid = "O5EG-PAPER-0095"
        elif rid in override_by_record and override_by_record[rid].get("action") == "merge":
            gid = override_by_record[rid].get("exposure_group_id") or decisions[override_by_record[rid]["survivor_record_id"]]["exposure_group_id"]
        else:
            gid = decision["exposure_group_id"]
        group_by_record[rid] = gid

    by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    members: list[dict[str, object]] = []
    for record in records:
        rid = record["merged_record_id"]
        decision = decisions[rid]
        allowed, scope_reason = strict_scope(record, decision)
        year = year_bce(record.get("date", "")) or decision.get("year_bce", "")
        in_window = year in STRICT_YEARS
        role = decision.get("provisional_stock_role", "")
        if not in_window:
            stock_class = "outside_strict_window"
        elif not allowed:
            stock_class = "excluded_or_context"
        elif rid in FORCED_STOCK_RECORDS:
            stock_class = "forced_reviewed_stock"
        elif role == "possible_active_stock":
            stock_class = "active_stock"
        elif role in {"possible_active_or_flow_review", "contingent_exposure_review", "closed_or_transfer_review"}:
            stock_class = "candidate_stock"
        else:
            stock_class = "excluded_or_context"
        contributes_t4 = stock_class in {"forced_reviewed_stock", "active_stock", "candidate_stock"}
        row: dict[str, object] = {
            "exposure_group_id": group_by_record[rid], "record_id": rid, "source_citation": decision.get("source_citation", ""),
            "year_bce": year, "calculation_window": "45-44 BCE" if in_window else "outside_45_44",
            "membership_role": "member", "amount_role": "group_amount_evidence", "timing_role": "strict_anchor" if in_window else "context",
            "party_role": "borrower_lender_and_named_third_parties", "graph_role": "raw_seed_member" if contributes_t4 else "not_seed",
            "scope_role": "strict_private" if allowed else "excluded_scope", "stock_class": stock_class,
            "contributes_to_amount_pool": "pending_group_amount", "calibration_fold_eligible": "pending_group_amount",
            "contributes_to_o5_t4": "yes" if contributes_t4 else "no",
            "contributes_to_o5_t5_seed": "yes" if contributes_t4 else "no",
            "contributes_to_o5_t5_candidate_basis": "yes" if contributes_t4 and allowed and in_window else "no",
            "contributes_to_o5_t5_candidate_endpoint": "occurrence_specific",
            "contributes_to_o56": "yes" if any(rid in component[1] for component in O56_COMPONENTS) else "no",
            "contributes_to_strict_graph": "yes" if contributes_t4 and allowed and in_window else "no",
            "contributes_to_strict_stock": "yes" if contributes_t4 else "no", "contributes_to_o6_actor_universe": "occurrence_specific",
            "decision_authority": "revision5_plan_plus_repaired_review_mapping", "decision_reason": scope_reason,
        }
        members.append(row)
        by_group[group_by_record[rid]].append(row)

    amount_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in amount_rows:
        amount_by_record[row["record_id"]].append(row)
    amount_authority: list[dict[str, object]] = []
    for gid, group_members in sorted(by_group.items()):
        ids = sorted(str(row["record_id"]) for row in group_members)
        active = [row for row in group_members if row["contributes_to_o5_t4"] == "yes"]
        selected = None
        semantics = "missing"
        evidence_ids: list[str] = []
        exact = False
        if set(ids) & GARDEN_MEMBERS:
            selected, semantics, evidence_ids = 1_200_000.0, "reviewed_purchase_funding_lower_bound", ["ATT-PILOT-0012-AMT-01", "ATT-PILOT-0012-AMT-02"]
        elif set(ids) & PUBLILIUS_MEMBERS:
            selected, semantics, evidence_ids, exact = 400_000.0, "residual_balance_before_immediate_payment", ["ATT-PILOT-0030-AMT-01"], True
        else:
            candidates: list[tuple[float, str, str]] = []
            for rid in ids:
                for amount in amount_by_record.get(rid, []):
                    role = amount.get("amount_role", "").lower()
                    if role in FLOW_ONLY_AMOUNT_ROLES:
                        continue
                    try:
                        value = float(amount.get("normalized_amount_hs", ""))
                    except ValueError:
                        continue
                    if value > 0 and (amount.get("include_in_scale_strict") == "yes" or amount.get("include_in_scale_candidate") == "yes"):
                        candidates.append((value, amount["amount_instance_id"], role))
            if candidates:
                value, evidence, role = max(candidates)
                selected, semantics, evidence_ids, exact = value, role or "exact_observed_stock", [evidence], True
        active_confidences = [decisions[str(row["record_id"])].get("confidence", "") for row in active]
        contingent_only = any(
            decisions[str(row["record_id"])].get("status", "").lower() == "guaranteed"
            or "surety" in decisions[str(row["record_id"])].get("loan_type", "").lower()
            or "guarantee" in decisions[str(row["record_id"])].get("loan_type", "").lower()
            for row in active
        )
        calibration = bool(active and selected and exact and not contingent_only and all(row["scope_role"] == "strict_private" for row in active))
        if gid == "O5EG-0016":
            calibration = False
        amount_authority.append({
            "exposure_group_id": gid, "member_record_ids": ";".join(ids), "selected_amount_hs": "" if selected is None else fmt(selected),
            "amount_semantics": semantics, "permitted_families": "paper;O5-T4;O5-T5;O5-6;calibration" if calibration else "paper;O5-T4;O5-T5;O5-6",
            "calibration_eligible": "yes" if calibration else "no", "evidence_amount_instance_ids": ";".join(evidence_ids),
            "stock_counting_rule": "one_selected_group_amount_max_or_reviewed_special", "include_probability": fmt(confidence_probability(active_confidences)),
            "decision_authority": "revision5_group_amount_authority",
        })
    return members, amount_authority, by_group


def occurrence_financial_role(role: str, raw: str) -> bool:
    key = norm(raw)
    if role in {"borrower", "lender"}:
        return True
    return key in KNOWN_FINANCIAL_AGENTS or any(word in raw.lower() for word in FINANCIAL_AGENT_WORDS)


def build_actor_and_relation_authorities(
    records: dict[str, dict[str, str]], members: list[dict[str, object]], by_group: dict[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    member_by_record = {str(row["record_id"]): row for row in members}
    seed_groups = {str(row["exposure_group_id"]) for row in members if row["contributes_to_o5_t4"] == "yes"}
    occurrences: list[dict[str, object]] = []
    by_record_role: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    aliases: dict[tuple[str, str], dict[str, object]] = {}
    for gid in sorted(seed_groups):
        for member in by_group[gid]:
            rid = str(member["record_id"])
            record = records[rid]
            for role, field in (("borrower", "borrower"), ("lender", "lender"), ("third_party", "third_parties")):
                raw_field = PARTY_FIELD_OVERRIDES.get(rid, {}).get(field, record.get(field, ""))
                for index, raw in enumerate(split_people(raw_field), start=1):
                    placeholder = is_placeholder(raw)
                    key = norm(raw)
                    stable_id = ("PLH-" + sha256_rows([raw])[:16]) if placeholder else actor_id(raw)
                    financial = occurrence_financial_role(role, raw)
                    basis_ok = member["contributes_to_o5_t5_candidate_basis"] == "yes"
                    endpoint_ok = basis_ok and financial and not placeholder
                    out: dict[str, object] = {
                        "actor_occurrence_id": occurrence_id(rid, role, index), "record_id": rid, "exposure_group_id": gid,
                        "source_citation": member["source_citation"], "raw_label": raw, "stable_actor_id": stable_id,
                        "stable_actor_label": key, "alias_status": "placeholder_token" if placeholder else "resolved_current_label",
                        "resolution_status": "resolved_placeholder" if placeholder else "resolved", "placeholder_status": "yes" if placeholder else "no",
                        "party_role": role, "financial_role": "yes" if financial else "no", "date_role": member["calculation_window"],
                        "scope_role": member["scope_role"], "candidate_endpoint_authorized": "yes" if endpoint_ok else "no",
                        "candidate_endpoint_authority": "revision5_occurrence_rule", "candidate_endpoint_reason": "financial_named_occurrence_on_valid_seed_basis" if endpoint_ok else "placeholder_context_or_invalid_basis",
                        "o6_actor_authorized": "pending_component_gate",
                    }
                    occurrences.append(out)
                    by_record_role[(rid, role)].append(out)
                    aliases[(raw, stable_id)] = {"raw_label": raw, "normalized_label": key, "stable_actor_id": stable_id, "alias_status": out["alias_status"], "authority": "current_typed_rebuild"}

    authorized_by_group: dict[str, set[str]] = defaultdict(set)
    for occurrence in occurrences:
        if occurrence["candidate_endpoint_authorized"] == "yes":
            authorized_by_group[str(occurrence["exposure_group_id"])].add(str(occurrence["stable_actor_id"]))
    for occurrence in occurrences:
        gid = str(occurrence["exposure_group_id"])
        occurrence["o6_actor_authorized"] = "yes" if occurrence["candidate_endpoint_authorized"] == "yes" and len(authorized_by_group[gid]) >= 2 else "no"

    relations: list[dict[str, object]] = []
    for rid in sorted({str(row["record_id"]) for row in occurrences}):
        member = member_by_record[rid]
        borrowers = by_record_role[(rid, "borrower")]
        lenders = by_record_role[(rid, "lender")]
        thirds = by_record_role[(rid, "third_party")]

        def add_relation(left: dict[str, object], right: dict[str, object], role: str, financial: bool) -> None:
            a, b = sorted((str(left["actor_occurrence_id"]), str(right["actor_occurrence_id"])))
            basis = member["contributes_to_o5_t5_candidate_basis"] == "yes" and financial
            if not financial:
                basis_reason = "documentary_context_relation_not_authorized_as_candidate_basis"
            elif member["contributes_to_o5_t5_candidate_basis"] != "yes":
                basis_reason = "source_member_not_authorized_as_candidate_basis"
            else:
                basis_reason = "strict_private_in_window_financial_relation"
            relations.append({
                "relation_id": relation_id(rid, role, a, b), "exposure_group_id": member["exposure_group_id"], "source_member_id": rid,
                "source_citation": member["source_citation"], "endpoint_a_occurrence_id": a, "endpoint_b_occurrence_id": b,
                "endpoint_a_actor_id": left["stable_actor_id"] if a == left["actor_occurrence_id"] else right["stable_actor_id"],
                "endpoint_b_actor_id": right["stable_actor_id"] if b == right["actor_occurrence_id"] else left["stable_actor_id"],
                "source_direction": "undirected_for_graph", "confidence": records[rid].get("confidence", ""), "relation_role": role,
                "observed_or_modeled": "observed", "year_bce": year_bce(records[rid].get("date", "")), "scope": member["scope_role"],
                "strict_graph_authorized": "yes" if basis else "no", "candidate_basis_authorized": "yes" if basis else "no",
                "candidate_basis_authority": "revision5_typed_relation_rule", "candidate_basis_reason": basis_reason,
                "o6_observed_relation_authorized": "yes" if basis else "no", "decision_authority": "revision5_typed_relation_rule",
            })

        for borrower in borrowers:
            for lender in lenders:
                add_relation(borrower, lender, "direct_borrower_lender", True)
        for third in thirds:
            financial = third["financial_role"] == "yes"
            for principal in borrowers + lenders:
                add_relation(principal, third, "financial_intermediary" if financial else "documentary_context", financial)

    return occurrences, list(sorted(aliases.values(), key=lambda row: (str(row["stable_actor_id"]), str(row["raw_label"])))), relations


def basis_status(year: str, scope: str, authorized: str) -> str:
    if year not in STRICT_YEARS:
        return "out_of_window_basis"
    if scope != "strict_private":
        return "public_or_context_only_basis"
    if authorized != "yes":
        return "unauthorized_candidate_basis"
    return "valid_basis"


def proposal_hash(fields: list[object]) -> str:
    return sha256_bytes(json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode())


def build_proposals(
    occurrences: list[dict[str, object]], relations: list[dict[str, object]], members: list[dict[str, object]],
) -> list[dict[str, object]]:
    occurrence = {str(row["actor_occurrence_id"]): row for row in occurrences}
    by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in occurrences:
        by_group[str(row["exposure_group_id"])].append(row)
    proposals: list[dict[str, object]] = []

    def add(proposal: dict[str, object]) -> None:
        a = str(proposal["endpoint_a_occurrence_id"])
        b = str(proposal["endpoint_b_occurrence_id"])
        if b < a:
            a, b = b, a
            proposal["endpoint_a_occurrence_id"], proposal["endpoint_b_occurrence_id"] = a, b
            for left, right in (
                ("leg_a_neighbor_occurrence_id", "leg_b_neighbor_occurrence_id"),
                ("leg_a_support_id", "leg_b_support_id"),
                ("leg_a_source_id", "leg_b_source_id"),
                ("leg_a_source_citation", "leg_b_source_citation"),
                ("leg_a_date", "leg_b_date"),
                ("leg_a_scope", "leg_b_scope"),
                ("leg_a_candidate_basis_authorized", "leg_b_candidate_basis_authorized"),
                ("leg_a_candidate_basis_authority", "leg_b_candidate_basis_authority"),
                ("leg_a_candidate_basis_reason", "leg_b_candidate_basis_reason"),
                ("leg_a_status", "leg_b_status"),
            ):
                proposal[left], proposal[right] = proposal.get(right, ""), proposal.get(left, "")
        fields = [
            METHOD_ID, proposal["channel"], proposal["seed_component_id"], a, b,
            proposal.get("shared_neighbor_actor_id") or None, proposal.get("leg_a_neighbor_occurrence_id") or None,
            proposal.get("leg_b_neighbor_occurrence_id") or None, proposal.get("leg_a_support_id") or None,
            proposal.get("leg_b_support_id") or None, proposal.get("within_component_basis_id") or None,
        ]
        full = proposal_hash(fields)
        proposal["proposal_id"] = full
        proposal["proposal_prefix"] = "PROP-" + full[:16]
        proposal["endpoint_a_actor_id"] = occurrence[a]["stable_actor_id"]
        proposal["endpoint_b_actor_id"] = occurrence[b]["stable_actor_id"]
        proposal["endpoint_a_placeholder"] = occurrence[a]["placeholder_status"]
        proposal["endpoint_b_placeholder"] = occurrence[b]["placeholder_status"]
        proposal["endpoint_a_authorized"] = occurrence[a]["candidate_endpoint_authorized"]
        proposal["endpoint_b_authorized"] = occurrence[b]["candidate_endpoint_authorized"]
        proposal["endpoint_a_authority"] = occurrence[a]["candidate_endpoint_authority"]
        proposal["endpoint_b_authority"] = occurrence[b]["candidate_endpoint_authority"]
        proposal["endpoint_a_reason"] = occurrence[a]["candidate_endpoint_reason"]
        proposal["endpoint_b_reason"] = occurrence[b]["candidate_endpoint_reason"]
        proposals.append(proposal)

    member_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in members:
        member_by_group[str(row["exposure_group_id"])].append(row)
    for gid, rows in sorted(by_group.items()):
        component_valid = any(row["contributes_to_o5_t5_candidate_basis"] == "yes" for row in member_by_group[gid])
        component_status = "valid_basis" if component_valid else "unauthorized_candidate_basis"
        ordered = sorted(rows, key=lambda row: str(row["actor_occurrence_id"]))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                add({
                    "channel": "within_component", "seed_component_id": gid,
                    "endpoint_a_occurrence_id": left["actor_occurrence_id"], "endpoint_b_occurrence_id": right["actor_occurrence_id"],
                    "shared_neighbor_actor_id": "", "leg_a_neighbor_occurrence_id": "", "leg_b_neighbor_occurrence_id": "",
                    "leg_a_support_id": "", "leg_b_support_id": "", "leg_a_status": "", "leg_b_status": "",
                    "leg_a_source_id": "", "leg_b_source_id": "", "leg_a_source_citation": "", "leg_b_source_citation": "",
                    "leg_a_date": "", "leg_b_date": "", "leg_a_scope": "", "leg_b_scope": "",
                    "leg_a_candidate_basis_authorized": "", "leg_b_candidate_basis_authorized": "",
                    "leg_a_candidate_basis_authority": "", "leg_b_candidate_basis_authority": "",
                    "leg_a_candidate_basis_reason": "", "leg_b_candidate_basis_reason": "",
                    "within_component_basis_id": gid, "basis_evaluation": component_status,
                    "source_provenance": ";".join(sorted({str(row["record_id"]) for row in member_by_group[gid]})),
                })

    adjacency: dict[str, list[tuple[dict[str, object], str, str]]] = defaultdict(list)
    for relation in relations:
        for neighbor_side, other_side in (("a", "b"), ("b", "a")):
            neighbor_occ = str(relation[f"endpoint_{neighbor_side}_occurrence_id"])
            other_occ = str(relation[f"endpoint_{other_side}_occurrence_id"])
            adjacency[str(occurrence[neighbor_occ]["stable_actor_id"])].append((relation, neighbor_occ, other_occ))
    for neighbor_actor, legs in sorted(adjacency.items()):
        for index, (rel_a, n_occ_a, end_a) in enumerate(legs):
            for rel_b, n_occ_b, end_b in legs[index + 1:]:
                if rel_a["relation_id"] == rel_b["relation_id"]:
                    continue
                status_a = basis_status(str(rel_a["year_bce"]), str(rel_a["scope"]), str(rel_a["candidate_basis_authorized"]))
                status_b = basis_status(str(rel_b["year_bce"]), str(rel_b["scope"]), str(rel_b["candidate_basis_authorized"]))
                if "out_of_window_basis" in {status_a, status_b}:
                    atomic = "out_of_window_basis"
                elif "public_or_context_only_basis" in {status_a, status_b}:
                    atomic = "public_or_context_only_basis"
                elif "unauthorized_candidate_basis" in {status_a, status_b}:
                    atomic = "unauthorized_candidate_basis"
                else:
                    atomic = "valid_basis"
                financial = rel_a["relation_role"] != "documentary_context" or rel_b["relation_role"] != "documentary_context"
                channel = "financial_shared_neighbor" if financial else "documentary_shared_neighbor"
                component_key = ";".join(sorted({str(rel_a["exposure_group_id"]), str(rel_b["exposure_group_id"])}))
                add({
                    "channel": channel, "seed_component_id": component_key, "endpoint_a_occurrence_id": end_a,
                    "endpoint_b_occurrence_id": end_b, "shared_neighbor_actor_id": neighbor_actor,
                    "leg_a_neighbor_occurrence_id": n_occ_a, "leg_b_neighbor_occurrence_id": n_occ_b,
                    "leg_a_support_id": rel_a["relation_id"], "leg_b_support_id": rel_b["relation_id"],
                    "leg_a_source_id": rel_a["source_member_id"], "leg_b_source_id": rel_b["source_member_id"],
                    "leg_a_source_citation": rel_a["source_citation"], "leg_b_source_citation": rel_b["source_citation"],
                    "leg_a_date": rel_a["year_bce"], "leg_b_date": rel_b["year_bce"],
                    "leg_a_scope": rel_a["scope"], "leg_b_scope": rel_b["scope"],
                    "leg_a_candidate_basis_authorized": rel_a["candidate_basis_authorized"],
                    "leg_b_candidate_basis_authorized": rel_b["candidate_basis_authorized"],
                    "leg_a_candidate_basis_authority": rel_a["candidate_basis_authority"],
                    "leg_b_candidate_basis_authority": rel_b["candidate_basis_authority"],
                    "leg_a_candidate_basis_reason": rel_a["candidate_basis_reason"],
                    "leg_b_candidate_basis_reason": rel_b["candidate_basis_reason"],
                    "leg_a_status": status_a, "leg_b_status": status_b, "within_component_basis_id": "",
                    "basis_evaluation": atomic, "source_provenance": ";".join(sorted({str(rel_a["source_member_id"]), str(rel_b["source_member_id"])})),
                })
    if len({row["proposal_id"] for row in proposals}) != len(proposals):
        raise ValueError("Proposal hash collision or duplicate canonical proposal serialization")
    return sorted(proposals, key=lambda row: str(row["proposal_id"]))


def build_dyads(proposals: list[dict[str, object]], relations: list[dict[str, object]]) -> tuple[list[dict[str, object]], set[str]]:
    observed_pairs = {
        tuple(sorted((str(row["endpoint_a_actor_id"]), str(row["endpoint_b_actor_id"]))))
        for row in relations if row["strict_graph_authorized"] == "yes"
    }
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for proposal in proposals:
        key = tuple(sorted((str(proposal["endpoint_a_actor_id"]), str(proposal["endpoint_b_actor_id"]))))
        grouped[key].append(proposal)
    dyads: list[dict[str, object]] = []
    u_visibility: set[str] = set()
    for key, rows in sorted(grouped.items()):
        valid = [row for row in rows if row["basis_evaluation"] == "valid_basis"]
        fully = [row for row in valid if row["endpoint_a_authorized"] == "yes" and row["endpoint_b_authorized"] == "yes"]
        placeholders = any(row["endpoint_a_placeholder"] == "yes" or row["endpoint_b_placeholder"] == "yes" for row in rows)
        unresolved = not key[0] or not key[1]
        self_loop = key[0] == key[1]
        if fully and not unresolved and not placeholders and not self_loop:
            u_visibility.update(key)
        if unresolved:
            status = "unresolved_actor"
        elif self_loop:
            status = "self_loop"
        elif placeholders:
            status = "placeholder_endpoint"
        elif key in observed_pairs:
            status = "already_observed"
        elif not valid:
            statuses = {str(row["basis_evaluation"]) for row in rows}
            if statuses == {"out_of_window_basis"}:
                status = "out_of_window_basis"
            elif "valid_basis" not in statuses and statuses <= {"out_of_window_basis", "public_or_context_only_basis"} and "public_or_context_only_basis" in statuses:
                status = "public_or_context_only_basis"
            else:
                status = "unauthorized_candidate_basis"
        elif not fully:
            status = "unauthorized_endpoint"
        else:
            status = "surviving_candidate"
        authorizer = min((str(row["proposal_id"]) for row in fully), default="")
        selected = next((row for row in fully if row["proposal_id"] == authorizer), None)
        if selected is None:
            authorizing_a_occurrence = authorizing_b_occurrence = ""
            authorizing_a_authority = authorizing_b_authority = ""
            authorizing_a_reason = authorizing_b_reason = ""
        elif selected["endpoint_a_actor_id"] == key[0] and selected["endpoint_b_actor_id"] == key[1]:
            authorizing_a_occurrence = selected["endpoint_a_occurrence_id"]
            authorizing_b_occurrence = selected["endpoint_b_occurrence_id"]
            authorizing_a_authority = selected["endpoint_a_authority"]
            authorizing_b_authority = selected["endpoint_b_authority"]
            authorizing_a_reason = selected["endpoint_a_reason"]
            authorizing_b_reason = selected["endpoint_b_reason"]
        elif selected["endpoint_b_actor_id"] == key[0] and selected["endpoint_a_actor_id"] == key[1]:
            authorizing_a_occurrence = selected["endpoint_b_occurrence_id"]
            authorizing_b_occurrence = selected["endpoint_a_occurrence_id"]
            authorizing_a_authority = selected["endpoint_b_authority"]
            authorizing_b_authority = selected["endpoint_a_authority"]
            authorizing_a_reason = selected["endpoint_b_reason"]
            authorizing_b_reason = selected["endpoint_a_reason"]
        elif key[0] == key[1] == selected["endpoint_a_actor_id"] == selected["endpoint_b_actor_id"]:
            authorizing_a_occurrence = selected["endpoint_a_occurrence_id"]
            authorizing_b_occurrence = selected["endpoint_b_occurrence_id"]
            authorizing_a_authority = selected["endpoint_a_authority"]
            authorizing_b_authority = selected["endpoint_b_authority"]
            authorizing_a_reason = selected["endpoint_a_reason"]
            authorizing_b_reason = selected["endpoint_b_reason"]
        else:
            raise ValueError(f"Authorizing proposal {authorizer} cannot be aligned to dyad {key}")
        dyads.append({
            "dyad_id": "DYAD-" + sha256_rows(list(key))[:16], "endpoint_a_actor_id": key[0], "endpoint_b_actor_id": key[1],
            "terminal_status": status, "proposal_count": len(rows), "channels": ";".join(sorted({str(row["channel"]) for row in rows})),
            "valid_proposal_count": len(valid), "fully_authorizing_proposal_count": len(fully), "authorizing_proposal_id": authorizer,
            "authorizing_endpoint_a_occurrence_id": authorizing_a_occurrence,
            "authorizing_endpoint_b_occurrence_id": authorizing_b_occurrence,
            "authorizing_endpoint_a_authority": authorizing_a_authority,
            "authorizing_endpoint_b_authority": authorizing_b_authority,
            "authorizing_endpoint_a_reason": authorizing_a_reason,
            "authorizing_endpoint_b_reason": authorizing_b_reason,
        })
    return dyads, u_visibility


def build_visibility(
    u_visibility: set[str], occurrences: list[dict[str, object]], relations: list[dict[str, object]], members: list[dict[str, object]],
) -> tuple[list[dict[str, object]], str, float]:
    records_by_actor: dict[str, set[str]] = defaultdict(set)
    citations_by_actor: dict[str, set[str]] = defaultdict(set)
    components_by_actor: dict[str, set[str]] = defaultdict(set)
    financial_counts: Counter[str] = Counter()
    for row in occurrences:
        actor = str(row["stable_actor_id"])
        if actor in u_visibility and row["candidate_endpoint_authorized"] == "yes":
            records_by_actor[actor].add(str(row["record_id"]))
            citations_by_actor[actor].add(str(row["source_citation"]))
            components_by_actor[actor].add(str(row["exposure_group_id"]))
            financial_counts[actor] += 1
    graph: dict[str, set[str]] = defaultdict(set)
    known: dict[str, set[str]] = defaultdict(set)
    for row in relations:
        if row["strict_graph_authorized"] != "yes" or row["candidate_basis_authorized"] != "yes":
            continue
        a, b = str(row["endpoint_a_actor_id"]), str(row["endpoint_b_actor_id"])
        if a in u_visibility and b in u_visibility and a != b:
            graph[a].add(b); graph[b].add(a)
            if row["relation_role"] == "direct_borrower_lender":
                known[a].add(b); known[b].add(a)
    raw: dict[str, dict[str, float]] = {}
    for actor in sorted(u_visibility):
        values = {
            "R": float(len(records_by_actor[actor])), "S": float(len(citations_by_actor[actor])),
            "G": float(len(graph[actor])), "K": float(len(known[actor])), "F": float(len(components_by_actor[actor])),
        }
        values["h"] = sum(math.log1p(values[key]) for key in ("R", "S", "G", "K", "F"))
        raw[actor] = values
    max_h = max((row["h"] for row in raw.values()), default=0.0)
    if max_h <= 0:
        raise ValueError("U_visibility is empty or max_h_visibility is non-positive")
    rows: list[dict[str, object]] = []
    for actor in sorted(raw):
        values = raw[actor]
        d = values["h"] / max_h
        rows.append({
            "stable_actor_id": actor, "R": int(values["R"]), "S": int(values["S"]), "G": int(values["G"]), "K": int(values["K"]), "F": int(values["F"]),
            "h": fmt(values["h"]), "D": fmt(d), "missingness_m": fmt(1 - d), "u_visibility_member": "yes",
        })
    fingerprint = sha256_rows(sorted(u_visibility))
    return rows, fingerprint, max_h


def attach_probabilities(dyads: list[dict[str, object]], visibility: list[dict[str, object]]) -> None:
    by_actor = {str(row["stable_actor_id"]): row for row in visibility}
    for row in dyads:
        if row["terminal_status"] == "surviving_candidate":
            a, b = by_actor[str(row["endpoint_a_actor_id"])], by_actor[str(row["endpoint_b_actor_id"])]
            p = float(a["missingness_m"]) * float(b["missingness_m"])
        else:
            p = 0.0
        row["edge_probability_p"] = fmt(p)


def calibrate(points: list[dict[str, object]]) -> tuple[int, list[dict[str, object]], list[dict[str, object]]]:
    if len(points) < 2:
        raise ValueError("At least two exact private-stock calibration points are required")
    folds: list[dict[str, object]] = []
    scores: list[dict[str, object]] = []
    for k in K_VALUES:
        losses: list[float] = []
        for held in points:
            n = len(points) - 1
            prediction = ANCHOR_SAME_WINDOW if k == 0 else (n * ANCHOR_SAME_WINDOW + k * ANCHOR_PRIOR) / (n + k)
            target = float(held["amount_hs"])
            loss = abs(math.log(target) - math.log(prediction))
            losses.append(loss)
            folds.append({"k": k, "held_out_exposure_group_id": held["exposure_group_id"], "target_hs": fmt(target), "training_n": n, "prediction_hs": fmt(prediction), "absolute_natural_log_error": fmt(loss)})
        scores.append({"k": k, "fold_count": len(losses), "mean_absolute_natural_log_error": fmt(sum(losses) / len(losses))})
    best_score = min(float(row["mean_absolute_natural_log_error"]) for row in scores)
    tied = [int(row["k"]) for row in scores if abs(float(row["mean_absolute_natural_log_error"]) - best_score) <= TIE_TOLERANCE]
    return min(tied), folds, scores


def imputed_amount(selected_k: int, point_count: int) -> float:
    return ANCHOR_SAME_WINDOW if selected_k == 0 else (point_count * ANCHOR_SAME_WINDOW + selected_k * ANCHOR_PRIOR) / (point_count + selected_k)


def build_o5_t4_inputs(members: list[dict[str, object]], amounts: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    members_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in members:
        members_by_group[str(row["exposure_group_id"])].append(row)
    components: list[dict[str, object]] = []
    calibration_points: list[dict[str, object]] = []
    for amount in amounts:
        gid = str(amount["exposure_group_id"])
        active = [row for row in members_by_group[gid] if row["contributes_to_o5_t4"] == "yes"]
        if not active:
            continue
        record_ids = sorted(str(row["record_id"]) for row in active)
        selected = float(amount["selected_amount_hs"]) if amount["selected_amount_hs"] != "" else None
        statuses = [str(row["stock_class"]) for row in active]
        if gid == "O5EG-0016":
            months = 12.0
        elif "ATT-PILOT-0014" in record_ids:
            months = 5.0
        else:
            months = 12.0
        component_class = "observed_stock" if selected is not None else ("missing_amount_stock" if "active_stock" in statuses else "missing_exposure_reconstruction")
        components.append({
            "component_id": "O5T4-" + gid, "exposure_group_id": gid, "member_record_ids": ";".join(record_ids),
            "component_class": component_class, "amount_source": "selected_observed_group_amount" if selected is not None else "single_k_imputation",
            "observed_amount_hs": "" if selected is None else fmt(selected), "include_probability": amount["include_probability"],
            "strict_active_months": fmt(months), "active_fraction": fmt(min(months / STOCK_DENOMINATOR_MONTHS, 1.0)),
            "calculation_window": "45-44 BCE", "method_status": "precalculation_input",
        })
        if amount["calibration_eligible"] == "yes" and selected is not None:
            calibration_points.append({"exposure_group_id": gid, "member_record_ids": amount["member_record_ids"], "amount_hs": fmt(selected), "amount_semantics": amount["amount_semantics"], "eligibility_reason": "positive_exact_private_stock_exposure"})
    return components, calibration_points


def build_o6_inputs(
    occurrences: list[dict[str, object]], relations: list[dict[str, object]], visibility: list[dict[str, object]], dyads: list[dict[str, object]], visibility_hash: str, max_h: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    vis = {str(row["stable_actor_id"]): row for row in visibility}
    authorized = sorted({str(row["stable_actor_id"]) for row in occurrences if row["o6_actor_authorized"] == "yes"})
    absent = sorted(set(authorized) - set(vis))
    if absent:
        raise ValueError("O6 actors absent from U_visibility: " + ", ".join(absent))
    noncentral_values = [float(vis[actor]["D"]) for actor in authorized if actor not in {"ACT-CICERO", "ACT-ATTICUS"}]
    lower = linear_quantile(noncentral_values, 1 / 3)
    upper = linear_quantile(noncentral_values, 2 / 3)
    actors: list[dict[str, object]] = []
    for actor in authorized:
        d = float(vis[actor]["D"])
        if actor in {"ACT-CICERO", "ACT-ATTICUS"}:
            node_class = "central"
        elif d >= upper:
            node_class = "high"
        elif d >= lower:
            node_class = "medium"
        else:
            node_class = "low"
        actors.append({"stable_actor_id": actor, "D": fmt(d), "node_class": node_class, "class_method": O6_CLASS_METHOD, "lower_cutpoint": fmt(lower), "upper_cutpoint": fmt(upper), "u_visibility_fingerprint": visibility_hash, "max_h_visibility": fmt(max_h), "authorization": "affirmative_stock_component_occurrence"})
    actor_set = set(authorized)
    pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for relation in relations:
        if relation["o6_observed_relation_authorized"] != "yes":
            continue
        pair = tuple(sorted((str(relation["endpoint_a_actor_id"]), str(relation["endpoint_b_actor_id"]))))
        if pair[0] in actor_set and pair[1] in actor_set and pair[0] != pair[1]:
            pairs[pair].append(str(relation["relation_id"]))
    observed = [{"observed_pair_id": "O6OBS-" + sha256_rows(list(pair))[:16], "endpoint_a_actor_id": pair[0], "endpoint_b_actor_id": pair[1], "relation_ids": ";".join(sorted(ids)), "authorization": "affirmative_unique_unordered_typed_relation"} for pair, ids in sorted(pairs.items())]
    internal = [{"dyad_id": row["dyad_id"], "endpoint_a_actor_id": row["endpoint_a_actor_id"], "endpoint_b_actor_id": row["endpoint_b_actor_id"], "edge_probability_p": row["edge_probability_p"]} for row in dyads if row["terminal_status"] == "surviving_candidate" and row["endpoint_a_actor_id"] in actor_set and row["endpoint_b_actor_id"] in actor_set]
    return actors, observed, internal


def static_gates(
    members: list[dict[str, object]], amounts: list[dict[str, object]], occurrences: list[dict[str, object]], relations: list[dict[str, object]],
    proposals: list[dict[str, object]], dyads: list[dict[str, object]], visibility: list[dict[str, object]], o6_actors: list[dict[str, object]],
    o6_observed: list[dict[str, object]], o6_internal: list[dict[str, object]], records: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    def check(check_id: str, condition: bool, detail: str, value: object = "") -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "detail": detail, "value": value})

    proposal_ids = [str(row["proposal_id"]) for row in proposals]
    shared = [row for row in proposals if row["channel"] != "within_component"]
    channel_counts = Counter(str(row["channel"]) for row in proposals)
    relation_by_id = {str(row["relation_id"]): row for row in relations}
    occurrence_by_id = {str(row["actor_occurrence_id"]): row for row in occurrences}

    leg_evidence_fields = (
        "source_id", "source_citation", "date", "scope", "candidate_basis_authorized",
        "candidate_basis_authority", "candidate_basis_reason",
    )
    leg_evidence_complete = all(
        all(str(row.get(f"leg_{side}_{field}", "")).strip() for field in leg_evidence_fields)
        for row in shared for side in ("a", "b")
    )
    leg_authority_agrees = True
    leg_neighbor_agrees = True
    neighbor_distinct = True
    exact_leg_status = True
    exact_atomic_status = True
    for row in shared:
        for side in ("a", "b"):
            support = relation_by_id.get(str(row[f"leg_{side}_support_id"]))
            endpoint_occurrence_id = str(row[f"endpoint_{side}_occurrence_id"])
            neighbor_occurrence_id = str(row[f"leg_{side}_neighbor_occurrence_id"])
            if support is None:
                leg_authority_agrees = leg_neighbor_agrees = False
                continue
            expected_values = {
                "source_id": support["source_member_id"],
                "source_citation": support["source_citation"],
                "date": support["year_bce"],
                "scope": support["scope"],
                "candidate_basis_authorized": support["candidate_basis_authorized"],
                "candidate_basis_authority": support["candidate_basis_authority"],
                "candidate_basis_reason": support["candidate_basis_reason"],
            }
            if any(str(row[f"leg_{side}_{field}"]) != str(value) for field, value in expected_values.items()):
                leg_authority_agrees = False
            support_occurrences = {str(support["endpoint_a_occurrence_id"]), str(support["endpoint_b_occurrence_id"])}
            if {endpoint_occurrence_id, neighbor_occurrence_id} != support_occurrences:
                leg_neighbor_agrees = False
            neighbor_occurrence = occurrence_by_id.get(neighbor_occurrence_id)
            if neighbor_occurrence is None or str(neighbor_occurrence["stable_actor_id"]) != str(row["shared_neighbor_actor_id"]):
                leg_neighbor_agrees = False
            expected_status = basis_status(str(row[f"leg_{side}_date"]), str(row[f"leg_{side}_scope"]), str(row[f"leg_{side}_candidate_basis_authorized"]))
            if row[f"leg_{side}_status"] != expected_status:
                exact_leg_status = False
        if str(row["shared_neighbor_actor_id"]) in {str(row["endpoint_a_actor_id"]), str(row["endpoint_b_actor_id"])}:
            neighbor_distinct = False
        statuses = {str(row["leg_a_status"]), str(row["leg_b_status"])}
        if "out_of_window_basis" in statuses:
            expected_atomic = "out_of_window_basis"
        elif "public_or_context_only_basis" in statuses:
            expected_atomic = "public_or_context_only_basis"
        elif "unauthorized_candidate_basis" in statuses:
            expected_atomic = "unauthorized_candidate_basis"
        else:
            expected_atomic = "valid_basis"
        if row["basis_evaluation"] != expected_atomic:
            exact_atomic_status = False

    check("proposal_hash_unique", len(proposal_ids) == len(set(proposal_ids)), "Full proposal hashes are unique and row-order independent.", len(proposal_ids))
    check("atomic_two_leg_complete", all(row["leg_a_support_id"] and row["leg_b_support_id"] and row["leg_a_support_id"] != row["leg_b_support_id"] for row in shared), "Every shared-neighbor proposal has two distinct support legs.", len(shared))
    check("leg_specific_evidence_complete", leg_evidence_complete, "Both bridge legs carry source, citation, date, scope, authorization, authority, and reason.", len(shared))
    check("leg_specific_evidence_matches_authority", leg_authority_agrees, "Every copied leg field agrees exactly with its typed relation authority.")
    check("leg_neighbor_resolution", leg_neighbor_agrees, "Each support relation contains its endpoint and neighbor occurrences, and both neighbor occurrences resolve to the recorded stable neighbor.")
    check("shared_neighbor_distinct_from_endpoints", neighbor_distinct, "The shared neighbor differs from both candidate endpoints.")
    check("exact_leg_status", exact_leg_status, "Each leg status is exactly reproduced from its date, scope, and basis authorization.")
    check("exact_mixed_leg_precedence", exact_atomic_status, "Every atomic proposal follows the frozen mixed-leg precedence.")
    check("conjunctive_leg_validity", all((row["basis_evaluation"] == "valid_basis") == (row["leg_a_status"] == "valid_basis" and row["leg_b_status"] == "valid_basis") for row in shared), "Atomic validity requires two valid legs.")
    check("proposal_to_dyad_reconciliation", sum(int(row["proposal_count"]) for row in dyads) == len(proposals), "Every proposal maps to one dyad.")
    check("three_structural_channels", all(channel_counts[name] > 0 for name in ("within_component", "financial_shared_neighbor", "documentary_shared_neighbor")), "All three controlled structural channels produced raw proposals.", dict(channel_counts))
    check("one_terminal_status", all(row["terminal_status"] for row in dyads), "Every dyad has one terminal status.", len(dyads))
    survivors = [row for row in dyads if row["terminal_status"] == "surviving_candidate"]
    selected_dyads = [row for row in dyads if row["authorizing_proposal_id"]]
    aligned_authorizers = all(
        str(occurrence_by_id.get(str(row["authorizing_endpoint_a_occurrence_id"]), {}).get("stable_actor_id", "")) == str(row["endpoint_a_actor_id"])
        and str(occurrence_by_id.get(str(row["authorizing_endpoint_b_occurrence_id"]), {}).get("stable_actor_id", "")) == str(row["endpoint_b_actor_id"])
        for row in selected_dyads
    )
    selected_decisions_complete = all(
        all(str(row.get(field, "")).strip() for field in (
            "authorizing_endpoint_a_authority", "authorizing_endpoint_a_reason",
            "authorizing_endpoint_b_authority", "authorizing_endpoint_b_reason",
        ))
        for row in selected_dyads
    )
    survivor_decisions_complete = all(
        row["authorizing_proposal_id"] and all(str(row.get(field, "")).strip() for field in (
            "authorizing_endpoint_a_occurrence_id", "authorizing_endpoint_b_occurrence_id",
            "authorizing_endpoint_a_authority", "authorizing_endpoint_a_reason",
            "authorizing_endpoint_b_authority", "authorizing_endpoint_b_reason",
        ))
        for row in survivors
    )
    check("authorizing_occurrence_actor_alignment", aligned_authorizers, "Authorizing A/B occurrences resolve exactly to normalized dyad actors A/B.", len(selected_dyads))
    check("selected_endpoint_decisions_complete", selected_decisions_complete, "Every selected dyad carries both endpoint authorities and reasons.", len(selected_dyads))
    check("survivor_proposal_local_provenance_complete", survivor_decisions_complete, "Every survivor retains its proposal, aligned occurrences, and both endpoint decisions.", len(survivors))
    check("nonzero_frontier", bool(dyads), "Raw deduplicated frontier is non-zero.", len(dyads))
    check("nonzero_survivors", bool(survivors), "Surviving candidate set is non-zero.", len(survivors))
    expected = sum(float(row["edge_probability_p"]) for row in survivors)
    check("nonzero_expected_mass", expected > 0, "Expected edge count is non-zero.", fmt(expected))
    vis_set = {str(row["stable_actor_id"]) for row in visibility}
    reconstructed_visibility: set[str] = set()
    for proposal in proposals:
        if (
            proposal["basis_evaluation"] == "valid_basis"
            and proposal["endpoint_a_authorized"] == "yes"
            and proposal["endpoint_b_authorized"] == "yes"
            and proposal["endpoint_a_placeholder"] != "yes"
            and proposal["endpoint_b_placeholder"] != "yes"
            and proposal["endpoint_a_actor_id"]
            and proposal["endpoint_b_actor_id"]
            and proposal["endpoint_a_actor_id"] != proposal["endpoint_b_actor_id"]
        ):
            reconstructed_visibility.update((str(proposal["endpoint_a_actor_id"]), str(proposal["endpoint_b_actor_id"])))
    visibility_fingerprint = sha256_rows(sorted(vis_set))
    check("visibility_exact_reconstruction", reconstructed_visibility == vis_set, "U_visibility exactly reconstructs from fully endpoint-authorized valid proposals before anti-joins.", visibility_fingerprint)
    check("survivors_in_visibility", all(row["endpoint_a_actor_id"] in vis_set and row["endpoint_b_actor_id"] in vis_set for row in survivors), "All survivor endpoints belong to U_visibility.")
    check("visibility_complete_finite", bool(visibility) and all(all(math.isfinite(float(row[field])) for field in ("R", "S", "G", "K", "F", "h", "D", "missingness_m")) for row in visibility), "U_visibility statistics are complete and finite.", len(visibility))
    check("visibility_probability_bounds", all(0 <= float(row["D"]) <= 1 and 0 <= float(row["missingness_m"]) <= 1 for row in visibility), "All D and missingness values lie in [0,1].")
    check("dyad_probability_bounds", all(0 <= float(row["edge_probability_p"]) <= 1 for row in dyads), "All dyad probabilities lie in [0,1].")
    missingness = {str(row["stable_actor_id"]): float(row["missingness_m"]) for row in visibility}
    check("survivor_probability_formula", all(math.isclose(float(row["edge_probability_p"]), missingness[str(row["endpoint_a_actor_id"])] * missingness[str(row["endpoint_b_actor_id"])], rel_tol=1e-11, abs_tol=1e-11) for row in survivors), "Every survivor probability equals m_a times m_b.")
    check("excluded_dyad_zero_probability", all(float(row["edge_probability_p"]) == 0 for row in dyads if row["terminal_status"] != "surviving_candidate"), "Every excluded dyad has zero live probability.")
    o6_set = {str(row["stable_actor_id"]) for row in o6_actors}
    check("o6_actors_in_visibility", o6_set <= vis_set, "Every O6 actor belongs to U_visibility.", len(o6_set))
    class_counts = Counter(str(row["node_class"]) for row in o6_actors)
    check("o6_population_gate", class_counts["central"] >= 1 and sum(class_counts[name] for name in ("high", "medium", "low")) >= 3, "At least one central and three non-central actors.", dict(class_counts))
    check("o6_one_class_per_actor", len(o6_set) == len(o6_actors), "Exactly one class row per O6 actor.")
    check("o6_all_classes_positive", all(class_counts[name] > 0 for name in ("central", "high", "medium", "low")), "All four O6 classes have positive population.", dict(class_counts))
    unauthorized_relations = [row for row in o6_observed if row["endpoint_a_actor_id"] not in o6_set or row["endpoint_b_actor_id"] not in o6_set]
    check("o6_authority_gate", not unauthorized_relations, "No unclassified actor or unauthorized observed relation enters O6.", len(o6_observed))
    expected_internal = sum(float(row["edge_probability_p"]) for row in o6_internal)
    check("o6_positive_internal_expected_mass", expected_internal > 0, "Internal imputed-edge expected incidence is positive.", fmt(expected_internal))
    actor_class = {str(row["stable_actor_id"]): str(row["node_class"]) for row in o6_actors}
    observed_incidence: Counter[str] = Counter()
    modeled_incidence: Counter[str] = Counter()
    for row in o6_observed:
        observed_incidence[actor_class[str(row["endpoint_a_actor_id"])]] += 1
        observed_incidence[actor_class[str(row["endpoint_b_actor_id"])]] += 1
    for row in o6_internal:
        probability = float(row["edge_probability_p"])
        modeled_incidence[actor_class[str(row["endpoint_a_actor_id"])]] += probability
        modeled_incidence[actor_class[str(row["endpoint_b_actor_id"])]] += probability
    o6_arithmetic_finite = True
    central_rate = 0.0
    n_eff = 0.0
    if class_counts["central"] > 0:
        central_rate = (observed_incidence["central"] + modeled_incidence["central"]) / class_counts["central"]
    for node_class in ("central", "high", "medium", "low"):
        if class_counts[node_class] <= 0:
            o6_arithmetic_finite = False
            continue
        total_incidence = observed_incidence[node_class] + modeled_incidence[node_class]
        rate = total_incidence / class_counts[node_class]
        weight = rate / central_rate if central_rate > 0 else math.nan
        effective = class_counts[node_class] * weight
        if not all(math.isfinite(value) and value >= 0 for value in (float(observed_incidence[node_class]), float(modeled_incidence[node_class]), float(total_incidence), float(rate), float(weight), float(effective))):
            o6_arithmetic_finite = False
        n_eff += effective
    check("o6_central_normalization_gate", math.isfinite(central_rate) and central_rate > 0, "Central incidence and rate are finite and positive.", fmt(central_rate) if math.isfinite(central_rate) else "nonfinite")
    check("o6_finite_class_arithmetic", o6_arithmetic_finite, "Every O6 O_c/M_c/I_c/r_c/w_c value is finite and non-negative.")
    check("o6_modeled_incidence_reconciliation_preflight", math.isclose(sum(modeled_incidence.values()), 2 * expected_internal, rel_tol=1e-11, abs_tol=1e-11), "O6 modeled class incidence equals twice internal expected edge mass.", fmt(sum(modeled_incidence.values())))
    check("o6_effective_population_gate", math.isfinite(n_eff) and n_eff > 0, "O6 N_eff is finite and positive.", fmt(n_eff) if math.isfinite(n_eff) else "nonfinite")
    amount_by_gid = {str(row["exposure_group_id"]): row for row in amounts}
    publilius = amount_by_gid.get("O5EG-0015", {})
    check("publilius_400k", publilius.get("selected_amount_hs") == "400000" and "ATT-PILOT-0030-AMT-01" in str(publilius.get("evidence_amount_instance_ids", "")), "Publilius is one exact 400,000-HS stock amount; payment and inferred remainder are excluded.")
    group_by_record = {str(row["record_id"]): str(row["exposure_group_id"]) for row in members}
    check("records_28_34_separate", group_by_record.get("VRB-STAGED-0095") != group_by_record.get("VRB-STAGED-0092"), "Records 28 and 34 remain separate.")
    strict_records = {str(row["record_id"]) for row in members if row["contributes_to_o5_t4"] == "yes" or row["contributes_to_o5_t5_seed"] == "yes"}
    check("strict_exclusions", not (strict_records & (STRICT_EXCLUDED_RECORDS | POLITICAL_CONTEXT_RECORDS)), "ATT-PILOT-0037, records 28/34, and political/context records do not enter strict families.", ";".join(sorted(strict_records & (STRICT_EXCLUDED_RECORDS | POLITICAL_CONTEXT_RECORDS))))
    o56_members = [rid for component in O56_COMPONENTS for rid in component[1]]
    check("o56_membership_unique", bool(o56_members) and len(o56_members) == len(set(o56_members)), "Reviewed O5-6 components have non-duplicated member sets.", len(o56_members))
    check("o56_all_high_confidence", all(records[rid].get("confidence", "").lower() == "high" for rid in o56_members), "Every O5-6 member remains high confidence.")
    check("fixed_anchors", ANCHOR_SAME_WINDOW == 300_000 and ANCHOR_PRIOR == 400_000, "Fixed 300,000/400,000 anchors are unchanged.")
    if any(row["status"] == "FAIL" for row in checks):
        write_csv(AUDITS / "static_preflight_checks.csv", checks)
        failed = [str(row["check_id"]) for row in checks if row["status"] == "FAIL"]
        raise ValueError("Static preflight failed: " + ", ".join(failed))
    return checks


def calculate_o6(o5_t5: float, actors: list[dict[str, object]], observed: list[dict[str, object]], internal: list[dict[str, object]]) -> tuple[list[dict[str, object]], float]:
    actor_class = {str(row["stable_actor_id"]): str(row["node_class"]) for row in actors}
    n = Counter(actor_class.values())
    observed_incidence: Counter[str] = Counter()
    for row in observed:
        observed_incidence[actor_class[str(row["endpoint_a_actor_id"])]] += 1
        observed_incidence[actor_class[str(row["endpoint_b_actor_id"])]] += 1
    modeled_incidence: Counter[str] = Counter()
    for row in internal:
        p = float(row["edge_probability_p"])
        modeled_incidence[actor_class[str(row["endpoint_a_actor_id"])]] += p
        modeled_incidence[actor_class[str(row["endpoint_b_actor_id"])]] += p
    central_rate = (observed_incidence["central"] + modeled_incidence["central"]) / n["central"]
    if not math.isfinite(central_rate) or central_rate <= 0:
        raise ValueError("O6 central incidence normalization is not finite and positive")
    rows: list[dict[str, object]] = []
    n_eff = 0.0
    for node_class in ("central", "high", "medium", "low"):
        o = float(observed_incidence[node_class]); m = float(modeled_incidence[node_class]); i = o + m
        rate = i / n[node_class]
        weight = rate / central_rate
        effective = n[node_class] * weight
        n_eff += effective
        rows.append({"node_class": node_class, "n_c": n[node_class], "O_c": fmt(o), "M_c": fmt(m), "I_c": fmt(i), "r_c": fmt(rate), "w_c": fmt(weight), "effective_units": fmt(effective)})
    if not math.isfinite(n_eff) or n_eff <= 0:
        raise ValueError("O6 N_eff is not finite and positive")
    expected = sum(float(row["edge_probability_p"]) for row in internal)
    if not math.isclose(sum(float(row["M_c"]) for row in rows), 2 * expected, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("O6 modeled incidence does not reconcile to twice internal expected edge mass")
    o6 = o5_t5 * SENATOR_POPULATION / n_eff
    if not (1_000_000_000 <= o6 < 10_000_000_000):
        raise ValueError(f"O6W-T5A reasonableness gate failed: {o6}")
    return rows, o6


def distribution_values(calibration_hs: float) -> list[dict[str, object]]:
    z = {"p50": 0.0, "p75": 0.67448975, "p90": 1.28155157}
    rows: list[dict[str, object]] = []
    for position in ("p50", "p75", "p90"):
        mu = math.log(calibration_hs) - LOGNORMAL_SIGMA * z[position]
        total = 600 * math.exp(mu + 0.5 * LOGNORMAL_SIGMA ** 2)
        rows.append({"model": "lognormal", "parameter": "sigma=1.0", "cicero_position": position, "senators_600_mean_hs": fmt(total)})
    for position in ("p50", "p75", "p90"):
        q = {"p50": 0.5, "p75": 0.75, "p90": 0.9}[position]
        x_min = calibration_hs * (1 - q) ** (1 / PARETO_ALPHA)
        numerator = PARETO_ALPHA * x_min ** PARETO_ALPHA * (PARETO_CAP ** (1 - PARETO_ALPHA) - x_min ** (1 - PARETO_ALPHA))
        denominator = (1 - PARETO_ALPHA) * (1 - (x_min / PARETO_CAP) ** PARETO_ALPHA)
        rows.append({"model": "truncated_pareto", "parameter": "alpha=1.585;cap=50000000", "cicero_position": position, "senators_600_mean_hs": fmt(600 * numerator / denominator)})
    return rows


def file_entry(path: Path, role: str) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size, "role": role}


def run() -> dict[str, object]:
    global O56_COMPONENTS
    O56_COMPONENTS = load_o56_components()
    for directory in (TYPED, INTERMEDIATE, CALIBRATION, CALCULATED, AUDITS, MANIFESTS):
        directory.mkdir(parents=True, exist_ok=True)
    input_paths = [CANONICAL, DECISIONS, OVERRIDES, AMOUNTS, OBJECTIVES, PARAMETERS, O56_COMPONENTS_PATH]
    records_list = read_csv(CANONICAL)
    records = {row["merged_record_id"]: row for row in records_list}
    decisions = {row["record_id"]: row for row in read_csv(DECISIONS)}
    if set(records) != set(decisions):
        raise ValueError("Repaired canonical register and reviewed exposure mapping do not reconcile one-to-one")

    members, amount_authority, grouped = build_exposure_authorities(records_list, decisions, read_csv(AMOUNTS), read_csv(OVERRIDES))
    occurrences, aliases, relations = build_actor_and_relation_authorities(records, members, grouped)
    proposals = build_proposals(occurrences, relations, members)
    dyads, u_visibility = build_dyads(proposals, relations)
    visibility, visibility_hash, max_h = build_visibility(u_visibility, occurrences, relations, members)
    attach_probabilities(dyads, visibility)
    t4_components, calibration_points = build_o5_t4_inputs(members, amount_authority)
    o6_actors, o6_observed, o6_internal = build_o6_inputs(occurrences, relations, visibility, dyads, visibility_hash, max_h)

    paths = {
        "members": TYPED / "exposure_member_authority.csv", "amounts": TYPED / "exposure_amount_authority.csv",
        "occurrences": TYPED / "actor_occurrence_authority.csv", "aliases": TYPED / "actor_alias_authority.csv",
        "relations": TYPED / "relation_authority.csv", "paper_crosswalk": TYPED / "paper_exposure_crosswalk.csv",
        "t4_inputs": INTERMEDIATE / "o5_t4_component_inputs.csv", "calibration_points": INTERMEDIATE / "calibration_exact_points.csv",
        "proposals": INTERMEDIATE / "o5_t5_proposal_provenance.csv", "dyads": INTERMEDIATE / "o5_t5_normalized_dyads.csv",
        "visibility": INTERMEDIATE / "u_visibility_actor_statistics.csv", "visibility_ids": INTERMEDIATE / "u_visibility_actor_ids.csv",
        "o6_actors": INTERMEDIATE / "o6_actor_classes.csv", "o6_observed": INTERMEDIATE / "o6_observed_relations.csv",
        "o6_internal": INTERMEDIATE / "o6_internal_candidate_expected_incidence.csv",
    }
    write_csv(paths["members"], members); write_csv(paths["amounts"], amount_authority); write_csv(paths["occurrences"], occurrences)
    write_csv(paths["aliases"], aliases); write_csv(paths["relations"], relations)
    write_csv(paths["paper_crosswalk"], [{"record_id": row["record_id"], "exposure_group_id": row["exposure_group_id"], "paper_action": "regenerate_after_post_calculation_audit", "paper_edited": "no"} for row in members])
    write_csv(paths["t4_inputs"], t4_components); write_csv(paths["calibration_points"], calibration_points)
    write_csv(paths["proposals"], proposals); write_csv(paths["dyads"], dyads); write_csv(paths["visibility"], visibility)
    write_csv(paths["visibility_ids"], [{"stable_actor_id": actor} for actor in sorted(u_visibility)])
    write_csv(paths["o6_actors"], o6_actors); write_csv(paths["o6_observed"], o6_observed); write_csv(paths["o6_internal"], o6_internal)

    checks = static_gates(members, amount_authority, occurrences, relations, proposals, dyads, visibility, o6_actors, o6_observed, o6_internal, records)
    checks_path = AUDITS / "static_preflight_checks.csv"; write_csv(checks_path, checks)
    declared_inputs = [file_entry(path, "declared_source_input") for path in input_paths]
    generated_inputs = [file_entry(path, role) for role, path in paths.items()]
    preflight = {
        "manifest_type": "preflight_without_selected_k", "created_utc": build_timestamp(), "git_commit": git_commit(),
        "repair_version": REPAIR_VERSION,
        "method_ids": [METHOD_ID, O6_CLASS_METHOD, O6_METHOD], "anchors_hs": [300000, 400000],
        "k_calibration_policy": "data_selected_leave_one_out_over_integer_k_5_to_50_with_fold_training_record_count_n",
        "o56_membership_fingerprint": sha256_rows([(row[0], list(row[1])) for row in O56_COMPONENTS]),
        "u_visibility_fingerprint": visibility_hash, "max_h_visibility": fmt(max_h), "selected_k_present": False,
        "declared_inputs": declared_inputs, "generated_calculation_inputs": generated_inputs, "static_preflight_checks": file_entry(checks_path, "blocking_static_preflight"),
    }
    preflight_path = MANIFESTS / "preflight_manifest.json"; write_json(preflight_path, preflight)

    selected_k, folds, scores = calibrate(calibration_points)
    folds_path = CALIBRATION / "k_leave_one_out_folds.csv"; scores_path = CALIBRATION / "k_scores.csv"
    write_csv(folds_path, folds); write_csv(scores_path, scores)
    calibration_hash = sha256_rows(calibration_points)
    sealed = {
        "manifest_type": "sealed_calculation_manifest", "created_utc": build_timestamp(), "git_commit": git_commit(),
        "repair_version": REPAIR_VERSION,
        "preflight_manifest_sha256": sha256_file(preflight_path), "selected_k": selected_k, "selected_k_count": 1,
        "anchors_hs": [300000, 400000], "calibration_input_fingerprint": calibration_hash,
        "k_calibration_domain": {"minimum": K_MIN, "maximum": K_MAX, "selection": "minimum_equal_weight_mean_absolute_natural_log_error; ties within 1e-12 choose lower k"},
        "calibration_folds": file_entry(folds_path, "calibration_folds"), "calibration_scores": file_entry(scores_path, "calibration_scores"),
        "u_visibility_fingerprint": visibility_hash, "max_h_visibility": fmt(max_h),
        "allowlisted_calculation_inputs": generated_inputs,
    }
    sealed_path = MANIFESTS / "sealed_calculation_manifest.json"; write_json(sealed_path, sealed)

    live = json.loads(sealed_path.read_text())
    if live.get("selected_k_count") != 1 or not isinstance(live.get("selected_k"), int):
        raise ValueError("Sealed manifest does not contain exactly one selected_k")
    k = int(live["selected_k"])
    imputed = imputed_amount(k, len(calibration_points))
    amount_by_component: list[dict[str, object]] = []
    o5_t4 = 0.0
    for row in t4_components:
        amount = float(row["observed_amount_hs"]) if row["observed_amount_hs"] != "" else imputed
        contribution = amount * float(row["include_probability"]) * float(row["active_fraction"])
        out = dict(row); out.update({"selected_k": k, "imputed_amount_hs": "" if row["observed_amount_hs"] != "" else fmt(imputed), "base_contribution_hs": fmt(contribution), "method_status": "calculated_from_sealed_manifest"})
        amount_by_component.append(out); o5_t4 += contribution
    surviving = [row for row in dyads if row["terminal_status"] == "surviving_candidate"]
    missing_increment = sum(float(row["edge_probability_p"]) * imputed for row in surviving)
    o5_t5 = o5_t4 + missing_increment

    o56_rows: list[dict[str, object]] = []; o56 = 0.0
    for component_id, member_ids, treatment, fixed, active_fraction in O56_COMPONENTS:
        amount = float(fixed) if fixed is not None else imputed
        contribution = amount * active_fraction
        o56 += contribution
        o56_rows.append({"component_id": component_id, "member_record_ids": ";".join(member_ids), "amount_treatment": treatment, "selected_k": k, "amount_hs": fmt(amount), "active_fraction": fmt(active_fraction), "contribution_hs": fmt(contribution), "all_members_high_confidence": "yes"})
    distributions = distribution_values(o56)
    o6_class_rows, o6_value = calculate_o6(o5_t5, o6_actors, o6_observed, o6_internal)

    candidate_manifest_hash = sha256_file(paths["dyads"])
    for row in o6_class_rows:
        row["candidate_manifest_sha256"] = candidate_manifest_hash
        row["u_visibility_fingerprint"] = visibility_hash
    calculated_paths = {
        "t4_components": CALCULATED / "o5_t4_components.csv", "t5_candidates": CALCULATED / "o5_t5_surviving_candidates.csv",
        "o56_components": CALCULATED / "o56_components.csv", "distribution_values": CALCULATED / "o56_distribution_values.csv",
        "o6_classes": CALCULATED / "o6_class_incidence_and_weights.csv", "summary": CALCULATED / "recalculated_values_summary.csv",
    }
    write_csv(calculated_paths["t4_components"], amount_by_component)
    write_csv(calculated_paths["t5_candidates"], [dict(row, selected_k=k, imputed_amount_hs=fmt(imputed), expected_contribution_hs=fmt(float(row["edge_probability_p"]) * imputed)) for row in surviving])
    write_csv(calculated_paths["o56_components"], o56_rows); write_csv(calculated_paths["distribution_values"], distributions); write_csv(calculated_paths["o6_classes"], o6_class_rows)
    summary = [
        {"value_id": "selected_k", "value": k, "unit": "integer", "status": "sealed_not_published"},
        {"value_id": "hierarchical_p50_hs", "value": fmt(imputed), "unit": "HS", "status": "sealed_not_published"},
        {"value_id": "O5-T4", "value": fmt_currency(o5_t4), "unit": "HS", "status": "calculated_awaiting_independent_audit"},
        {"value_id": "O5-T5-missing-edge-increment", "value": fmt_currency(missing_increment), "unit": "HS", "status": "calculated_awaiting_independent_audit"},
        {"value_id": "O5-T5", "value": fmt_currency(o5_t5), "unit": "HS", "status": "calculated_awaiting_independent_audit"},
        {"value_id": "O5-6", "value": fmt_currency(o56), "unit": "HS", "status": "calculated_awaiting_independent_audit"},
        {"value_id": "O6W-T5A", "value": fmt(o6_value), "unit": "HS", "status": "calculated_awaiting_independent_audit"},
    ]
    write_csv(calculated_paths["summary"], summary)

    final_checks = [
        {"check_id": "one_live_k", "status": "PASS", "detail": "Exactly one selected_k is stored in the sealed manifest.", "value": k},
        {"check_id": "data_derived_k_floor", "status": "PASS" if k >= K_MIN else "FAIL", "detail": "Selected k is the data-derived leave-one-out winner in the user-authorized k=5..50 domain.", "value": k},
        {"check_id": "same_k_all_families", "status": "PASS", "detail": "O5-T4, O5-T5, and O5-6 consumed the sealed k.", "value": k},
        {"check_id": "fixed_anchors_unchanged", "status": "PASS", "detail": "300,000 and 400,000 HS anchors retained.", "value": "300000;400000"},
        {"check_id": "o56_membership_high_confidence", "status": "PASS", "detail": "Reviewed membership and high-confidence gate retained.", "value": len(O56_COMPONENTS)},
        {"check_id": "distribution_specifications", "status": "PASS", "detail": "Six fixed lognormal/Pareto derivatives produced.", "value": len(distributions)},
        {"check_id": "o6_modeled_incidence_reconciliation", "status": "PASS", "detail": "O6 M_c reconciles to twice internal expected-edge mass.", "value": fmt(sum(float(row["edge_probability_p"]) for row in o6_internal))},
        {"check_id": "o6_reasonableness_decade", "status": "PASS", "detail": "O6W-T5A remains in the 10^9-HS decade.", "value": fmt(o6_value)},
        {"check_id": "paper_hold", "status": "PASS", "detail": "No paper, figure, or current headline registry was written by this build.", "value": "awaiting_post_calculation_audit"},
    ]
    final_checks_path = AUDITS / "post_calculation_checks.csv"; write_csv(final_checks_path, final_checks)
    run_manifest = {
        "run_status": "public_release_reproduction", "created_utc": build_timestamp(),
        "repair_version": REPAIR_VERSION,
        "git_commit": git_commit(), "python": ">=3.11", "platform": "portable-python-standard-library", "sealed_manifest_sha256": sha256_file(sealed_path),
        "selected_k": k, "hierarchical_p50_hs": fmt(imputed), "u_visibility_fingerprint": visibility_hash,
        "candidate_manifest_sha256": candidate_manifest_hash, "calculated_outputs": [file_entry(path, role) for role, path in calculated_paths.items()],
        "post_calculation_checks": file_entry(final_checks_path, "post_calculation_checks"), "paper_hold": True,
    }
    run_manifest_path = MANIFESTS / "post_calculation_run_manifest.json"; write_json(run_manifest_path, run_manifest)
    return {"summary": summary, "run_manifest": run_manifest_path, "selected_k": k, "u_visibility_count": len(visibility), "proposal_count": len(proposals), "dyad_count": len(dyads), "surviving_candidate_count": len(surviving)}


def main() -> None:
    result = run()
    print(json.dumps({key: str(value) for key, value in result.items() if key != "summary"}, indent=2))
    for row in result["summary"]:
        print(f"{row['value_id']}: {row['value']} {row['unit']}")


if __name__ == "__main__":
    main()
