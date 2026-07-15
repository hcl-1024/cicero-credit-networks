#!/usr/bin/env python3
"""Build the paper's denominator, density, and probability-rule sensitivities."""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V5 = ROOT / "results" / "official" / "objective_05_06" / "recalculation_v5"
CALCULATED = V5 / "calculated"
INTERMEDIATE = V5 / "intermediate"
OUTPUT = V5 / "sensitivity"
SENATOR_POPULATION = 600


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def fmt(value: float, places: int = 6) -> str:
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def probability(rule: str, a: float, b: float) -> float:
    return {
        "product_current": a * b,
        "bottleneck_min": min(a, b),
        "capped_average": min((a + b) / 2, 0.75),
        "average_undercoverage": (a + b) / 2,
        "union_either_endpoint": 1 - (1 - a) * (1 - b),
    }[rule]


def o5_t4_for_amount(components: list[dict[str, str]], amount: float) -> float:
    total = 0.0
    for row in components:
        principal = float(row["observed_amount_hs"]) if row["observed_amount_hs"] else amount
        total += principal * float(row["include_probability"]) * float(row["active_fraction"])
    return total


def class_arithmetic(
    actors: list[dict[str, str]],
    observed: list[dict[str, str]],
    candidates: list[dict[str, str]],
    probabilities: dict[str, float],
) -> tuple[list[dict[str, object]], float, float]:
    actor_class = {row["stable_actor_id"]: row["node_class"] for row in actors}
    class_counts = Counter(actor_class.values())
    observed_incidence: dict[str, float] = defaultdict(float)
    modeled_incidence: dict[str, float] = defaultdict(float)
    for row in observed:
        observed_incidence[actor_class[row["endpoint_a_actor_id"]]] += 1
        observed_incidence[actor_class[row["endpoint_b_actor_id"]]] += 1
    for row in candidates:
        value = probabilities[row["dyad_id"]]
        modeled_incidence[actor_class[row["endpoint_a_actor_id"]]] += value
        modeled_incidence[actor_class[row["endpoint_b_actor_id"]]] += value
    central_rate = (observed_incidence["central"] + modeled_incidence["central"]) / class_counts["central"]
    result: list[dict[str, object]] = []
    effective_population = 0.0
    for node_class in ("central", "high", "medium", "low"):
        n_c = class_counts[node_class]
        o_c = observed_incidence[node_class]
        m_c = modeled_incidence[node_class]
        rate = (o_c + m_c) / n_c if n_c else 0.0
        weight = rate / central_rate
        units = n_c * weight
        effective_population += units
        result.append({
            "node_class": node_class, "n_c": n_c, "O_c": fmt(o_c, 12), "M_c": fmt(m_c, 12),
            "I_c": fmt(o_c + m_c, 12), "r_c": fmt(rate, 12), "w_c": fmt(weight, 12),
            "effective_units": fmt(units, 12),
        })
    expected_mass = sum(probabilities.values())
    if not math.isclose(sum(float(row["M_c"]) for row in result), 2 * expected_mass, abs_tol=1e-9):
        raise ValueError("O6 modeled incidence does not reconcile")
    return result, effective_population, expected_mass


def main() -> None:
    summary = {row["value_id"]: float(row["value"]) for row in read_csv(CALCULATED / "recalculated_values_summary.csv")}
    actors = read_csv(INTERMEDIATE / "o6_actor_classes.csv")
    observed = read_csv(INTERMEDIATE / "o6_observed_relations.csv")
    candidates = read_csv(INTERMEDIATE / "o6_internal_candidate_expected_incidence.csv")
    visibility = {row["stable_actor_id"]: row for row in read_csv(INTERMEDIATE / "u_visibility_actor_statistics.csv")}
    t4_components = read_csv(CALCULATED / "o5_t4_components.csv")
    base_t4 = o5_t4_for_amount(t4_components, 362_500)
    current = {row["dyad_id"]: float(row["edge_probability_p"]) for row in candidates}
    _, base_n_eff, _ = class_arithmetic(actors, observed, candidates, current)

    probability_rows: list[dict[str, object]] = []
    class_rows: list[dict[str, object]] = []
    for rule in ("product_current", "bottleneck_min", "capped_average", "average_undercoverage", "union_either_endpoint"):
        probabilities = {
            row["dyad_id"]: probability(rule, float(visibility[row["endpoint_a_actor_id"]]["missingness_m"]), float(visibility[row["endpoint_b_actor_id"]]["missingness_m"]))
            for row in candidates
        }
        classes, n_eff, expected_mass = class_arithmetic(actors, observed, candidates, probabilities)
        increment = expected_mass * 362_500
        t5 = base_t4 + increment
        probability_rows.append({
            "probability_rule": rule, "candidate_count": len(candidates), "expected_edge_mass": fmt(expected_mass, 12),
            "imputed_amount_hs": "362500", "o5_t4_hs": fmt(base_t4), "missing_edge_increment_hs": fmt(increment),
            "o5_t5_hs": fmt(t5), "o6_effective_population": fmt(n_eff, 12),
            "o6w_t5a_hs": fmt(round(t5 * SENATOR_POPULATION / n_eff)),
            "scenario_status": "selected_base" if rule == "product_current" else "diagnostic_not_selected",
        })
        class_rows.extend({"probability_rule": rule, **row} for row in classes)

    zero = {row["dyad_id"]: 0.0 for row in candidates}
    _, observed_n_eff, _ = class_arithmetic(actors, observed, candidates, zero)
    t5 = summary["O5-T5"]
    denominator_rows = [
        {"denominator_policy": "observed_incidence_only", "o5_t5_hs": fmt(t5), "effective_population": fmt(observed_n_eff, 12), "o6w_t5a_hs": fmt(round(t5 * SENATOR_POPULATION / observed_n_eff)), "status": "diagnostic_not_selected", "notes": "Uses authorized observed O6 relations and no modeled incidence."},
        {"denominator_policy": "observed_plus_internal_imputed_incidence", "o5_t5_hs": fmt(t5), "effective_population": fmt(base_n_eff, 12), "o6w_t5a_hs": fmt(round(t5 * SENATOR_POPULATION / base_n_eff)), "status": "selected_base", "notes": "Uses the same 199 audited internal candidates and their product-rule expected incidence."},
        {"denominator_policy": "equal_actor_unweighted", "o5_t5_hs": fmt(t5), "effective_population": fmt(len(actors), 12), "o6w_t5a_hs": fmt(round(t5 * SENATOR_POPULATION / len(actors))), "status": "diagnostic_not_selected", "notes": "Treats every authorized U_visibility actor as one effective unit."},
    ]
    multiplier = SENATOR_POPULATION / base_n_eff
    discounts = [(f"{value:g}x", value) for value in (1, 2, 3, 5, 10, 15, 20, 25)] + [("no_extrapolation", multiplier)]
    density_rows = [{
        "scenario": label, "density_discount": fmt(discount, 12), "effective_multiplier": fmt(multiplier / discount, 12),
        "recalculated_total_hs": fmt(round(summary["O6W-T5A"] / discount)),
        "ratio_to_600m_benchmark": fmt(summary["O6W-T5A"] / discount / 600_000_000, 6),
        "scenario_status": "selected_undiscounted" if discount == 1 else "diagnostic_not_selected",
    } for label, discount in discounts]

    write_csv(OUTPUT / "missing_edge_probability_rule_sensitivity.csv", probability_rows)
    write_csv(OUTPUT / "missing_edge_probability_rule_o6_classes.csv", class_rows)
    write_csv(OUTPUT / "o6_denominator_policy_sensitivity.csv", denominator_rows)
    write_csv(OUTPUT / "density_discount_sensitivity.csv", density_rows)
    print("Additional paper sensitivities reproduced: 5 probability rules, 3 denominator policies, 9 density scenarios")


if __name__ == "__main__":
    main()
