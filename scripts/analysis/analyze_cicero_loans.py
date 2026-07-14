#!/usr/bin/env python3
"""Build third-party-aware analysis tables for the Cicero loan dataset."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "canonical"
CANONICAL = PROCESSED
LEDGERS = PROCESSED / "ledgers"
ANALYSIS = ROOT / "build" / "analysis"
CORE = ANALYSIS / "core"
SUMMARIES = ANALYSIS / "summaries"
AUDITS = ANALYSIS / "audits"
ARCHIVE = ROOT / "build" / "archive" / "data"
SOURCE = CANONICAL / "cicero_credit_records.csv"
REJECTED_SOURCE = LEDGERS / "cicero_loan_rejected_candidates.csv"


ANALYSIS_FIELDS = [
    "record_id",
    "collection",
    "book",
    "letter",
    "source_letter_id",
    "year_bce",
    "decade_bce",
    "sender",
    "recipient",
    "borrower",
    "lender",
    "third_parties",
    "third_party_count",
    "has_third_parties",
    "third_party_involvement_types",
    "third_party_involvement_summary",
    "status",
    "loan_type",
    "analysis_loan_type",
    "confidence",
    "amount",
    "currency_or_unit",
    "amount_present",
    "normalized_amount_hs",
    "amount_certainty",
    "amount_review_needed",
    "borrower_category",
    "lender_category",
    "cicero_role",
    "atticus_role",
    "episode_group",
    "party_summary",
    "latin_evidence",
    "english_evidence",
    "interpretive_note",
    "source_url_or_edition",
]

PARTY_FIELDS = [
    "record_id",
    "collection",
    "source_letter_id",
    "year_bce",
    "episode_group",
    "role_type",
    "party_name",
    "canonical_party",
    "role_detail",
    "raw_value",
    "is_direct_party",
    "is_third_party",
    "confidence",
]

EDGE_FIELDS = [
    "record_id",
    "collection",
    "source_letter_id",
    "year_bce",
    "episode_group",
    "source_party",
    "source_canonical",
    "target_party",
    "target_canonical",
    "edge_type",
    "role_detail",
    "confidence",
]

INVOLVEMENT_FIELDS = [
    "record_id",
    "collection",
    "source_letter_id",
    "year_bce",
    "episode_group",
    "third_party",
    "canonical_party",
    "involvement_type",
    "involvement_summary",
    "borrower",
    "lender",
    "loan_type",
    "status",
    "confidence",
]

LABEL_PROVENANCE_FIELDS = [
    "record_id",
    "collection",
    "source_letter_id",
    "role_type",
    "source_field",
    "legacy_value",
    "analysis_value",
    "disposition",
]

AMOUNT_PROFILE_FIELDS = [
    "analysis_loan_type",
    "record_count",
    "amount_present_count",
    "normalized_hs_record_count",
    "amount_review_needed_count",
    "no_amount_count",
    "total_normalized_amount_hs",
    "min_normalized_amount_hs",
    "max_normalized_amount_hs",
    "normalized_amount_note",
]

TIMELINE_TYPE_FIELDS = [
    "year_bce",
    "decade_bce",
    "analysis_loan_type",
    "confidence",
    "record_count",
    "amount_present_count",
    "normalized_hs_record_count",
    "amount_review_needed_count",
]

REJECTED_TRIGGER_FIELDS = [
    "matched_term",
    "rejected_count",
    "top_rejection_reasons",
    "policy_note",
    "collections",
]

AMOUNT_TRIAGE_FIELDS = [
    "record_id",
    "source_letter_id",
    "analysis_loan_type",
    "amount",
    "currency_or_unit",
    "amount_triage",
    "triage_reason",
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [normalize_source_row(row) for row in csv.DictReader(handle)]


def normalize_source_row(row: dict[str, str]) -> dict[str, str]:
    if not row.get("record_id"):
        row["record_id"] = (
            row.get("canonical_record_id")
            or row.get("merged_record_id")
            or row.get("representative_record_id")
            or ""
        )
    return row


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


FINAL_ANALYSIS_TEXT_REPLACEMENTS = {
    "failed property sale": "failed sale context",
    "P. Varius estate / A. Caninius Satyrus as opposing party": "P. Varius; A. Caninius Satyrus",
    "Caecilius and other creditors": "Caecilius",
    "Atticus or associates seeking funds": "",
    "Atticus' steward and others": "",
    "Chersonese property accounts": "",
    "Cicero/Terentia household accounts": "",
    "Iunius or party represented by Iunius": "Iunius",
    "Pompey or Pompeian cause": "Pompey",
    "Terentia or secured party": "",
    "Terentia or party secured through Terentia": "",
    "unnamed payee known to Terentia and Tullia": "",
    "unspecified lender at high interest": "",
    "unspecified refinancing source": "",
    "unspecified claimant in Mescinius inheritance matter": "",
    "unspecified lender": "",
    "future versura lender unspecified": "",
    "possibly Curius as fallback": "Curius",
}


def clean_final_analysis_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = value
    for old, new in FINAL_ANALYSIS_TEXT_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    cleaned = re.sub(r";\s*;", ";", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"=\s*;", "=", cleaned)
    return cleaned.strip()


def clean_final_analysis_row(row: dict[str, object]) -> dict[str, object]:
    return {key: clean_final_analysis_text(value) for key, value in row.items()}


def infer_year_bce(date_text: str, source_letter_id: str) -> str:
    text = f"{date_text} {source_letter_id}"
    bracket_exact = re.search(r"\[(\d{1,3}) BCE\]", text)
    if bracket_exact:
        return bracket_exact.group(1)
    paren_years = re.findall(r"\((\d{2})\)", text)
    if paren_years:
        return paren_years[-1]
    auc_match = re.search(r"a\.?\s*u\.?\s*c\.?\s*(\d{3})", text, re.I)
    if not auc_match:
        auc_match = re.search(r"a\.\s*(\d{3})", text, re.I)
    if auc_match:
        return str(754 - int(auc_match.group(1)))
    return ""


def decade_bce(year: str) -> str:
    if not year:
        return ""
    value = int(year)
    return f"{value // 10 * 10}s BCE"


def split_parties(value: str) -> list[str]:
    if not value.strip():
        return []
    lowered = value.strip().lower()
    if lowered == "caecilius and other creditors":
        return ["Caecilius"]
    if lowered == "p. varius estate / a. caninius satyrus as opposing party":
        return ["P. Varius", "A. Caninius Satyrus"]
    if value.strip().lower() == "ofillius and aurelius":
        return ["Ofillius", "Aurelius"]
    pieces = []
    for piece in value.split(";"):
        piece = piece.strip()
        if piece:
            pieces.append(piece)
    return pieces


def join_parties(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(value for value in values if value))


def involvement_type_for(party: str, row: dict[str, str]) -> str:
    specific = {
        ("ATT-PILOT-0001", "L. Lucullus"): "co-creditor/legal claim context",
        ("ATT-PILOT-0001", "P. Scipio"): "co-creditor/legal claim context",
        ("ATT-PILOT-0001", "L. Pontius"): "estate-sale/legal manager",
        ("ATT-PILOT-0003", "Atticus as facilitator"): "manager/agent/procurator",
        ("ATT-PILOT-0003", "Oppius as Caesar-linked intermediary"): "payment/account intermediary",
        ("ATT-PILOT-0003", "Philotimus as account agent"): "manager/agent/procurator",
        ("ATT-PILOT-0005", "Q. Titinius"): "liquidity context",
        ("ATT-PILOT-0005", "L. Ligus"): "liquidity context",
        ("ATT-PILOT-0006", "Curius"): "fallback lender/helper",
        ("ATT-PILOT-0007", "Q. Axius"): "family/borrower-identification context",
        ("ATT-PILOT-0008", "Axius"): "related amount/account context",
        ("ATT-PILOT-0010", "Quintus"): "family/household context",
        ("ATT-PILOT-0012", "Hermogenes"): "payment source/collection target",
        ("ATT-PILOT-0016", "Balbus"): "manager/agent/procurator",
        ("ATT-PILOT-0017", "Cluvian estate"): "estate/coheir context",
        ("ATT-PILOT-0017", "Atticus as manager"): "manager/agent/procurator",
        ("ATT-PILOT-0018", "Cicero"): "failed set-aside/promisor context",
        ("ATT-PILOT-0018", "Montanus"): "underlying obligation context",
        ("ATT-PILOT-0018", "Dolabella"): "expected payment source",
        ("ATT-PILOT-0023", "Cn. Sallustius"): "payment source/collection target",
        ("ATT-PILOT-0025", "Cornificius' procurators"): "manager/agent/procurator",
        ("ATT-PILOT-0027", "Flaminius, for whom Montanus is surety"): "principal in surety relationship",
        ("ATT-PILOT-0028", "Faberius"): "debt-relief/payment channel",
        ("FAM-PILOT-0001", "Crassus"): "purchase/property context",
        ("FAM-PILOT-0003", "Oppia, widow of Mindius"): "inheritance/business context",
        ("QFR-PILOT-0001", "Marcus Tullius Cicero as payer/intermediary"): "payment intermediary",
        ("ATT-PILOT-0036", "Atticus as manager"): "manager/agent/procurator",
        ("ATT-PILOT-0037", "Atticus"): "manager/agent/procurator",
    }
    if (row["record_id"], party) in specific:
        return specific[(row["record_id"], party)]
    text = " ".join(
        [
            party,
            row["record_id"],
            row["borrower"],
            row["lender"],
            row["third_parties"],
            row["loan_type"],
            row["interest_or_terms"],
            row["interpretive_note"],
        ]
    ).lower()
    if "sponsor" in text or "guarantor" in text or "surety" in text or "praediator" in text or "satis dato" in text or "sponsores" in text:
        return "surety/guarantee actor"
    if "manager" in text or "agent" in text or "steward" in text or "procurator" in text or "procuratores" in text or "remittance" in text or "credit manager" in text:
        return "manager/agent/procurator"
    if "payer/intermediary" in text or "intermediary" in text or "payment source" in text or "collection agent" in text:
        return "payment intermediary"
    if "estate" in text or "coheir" in text or "cohered" in text or "inheritance" in text:
        return "estate/coheir context"
    if "account" in text or "nomina" in text or "nomen" in text or "faberius" in text or "camillus" in text or "eros" in text or "tiro" in text:
        return "accounting/bookkeeping context"
    if "family" in text or "terentia" in text or "quintus" in text:
        return "family/household context"
    if "seller" in text or "purchase" in text or "gardens" in text or "crassus" in text:
        return "purchase/property context"
    return "contextual associated party"


def involvement_summary_for(party: str, row: dict[str, str]) -> str:
    rid = row["record_id"]
    borrower = row["borrower"]
    lender = row["lender"]
    specific = {
        ("ATT-PILOT-0001", "L. Lucullus"): "Co-creditor in the creditor group pursuing the Varius/Satyrus claim.",
        ("ATT-PILOT-0001", "P. Scipio"): "Co-creditor in the creditor group pursuing the Varius/Satyrus claim.",
        ("ATT-PILOT-0001", "L. Pontius"): "Expected manager/magister if the debtor's goods were sold.",
        ("ATT-PILOT-0003", "Atticus as facilitator"): "Facilitates Cicero's effort to settle the Caesar/Oppius account while Cicero is away.",
        ("ATT-PILOT-0003", "Oppius as Caesar-linked intermediary"): "Intermediary through whom the account matter with Caesar's nomen is handled.",
        ("ATT-PILOT-0003", "Philotimus as account agent"): "Account agent available to Atticus for completing and checking the Oppius/Caesar account thread.",
        ("ATT-PILOT-0005", "Q. Titinius"): "Named in the surrounding cash/liquidity context for Quintus' inability to pay.",
        ("ATT-PILOT-0005", "L. Ligus"): "Named in the surrounding cash/liquidity context for Quintus' inability to pay.",
        ("ATT-PILOT-0006", "Curius"): "Fallback helper Cicero had asked to supply Tiro if funds were needed.",
        ("ATT-PILOT-0007", "Q. Axius"): "Father of the borrower; anchors the unpaid loan to Axius' son.",
        ("ATT-PILOT-0008", "Axius"): "Associated 12,000 HS matter tied to Quintus' refinancing problem.",
        ("ATT-PILOT-0010", "Quintus"): "Family context for Cicero's necessary borrowing after resources were spent.",
        ("ATT-PILOT-0012", "Hermogenes"): "Person from whom funds are to be extracted for the Silius/Faberius bridge payment.",
        ("ATT-PILOT-0013", "Eros"): "Household/account agent connected to the expected balances that force Cicero to borrow.",
        ("ATT-PILOT-0013", "Tiro"): "Household/account agent connected to the expected balances that force Cicero to borrow.",
        ("ATT-PILOT-0014", "Quintus"): "Expected source of funds due by the term of Cicero's five-month versura.",
        ("ATT-PILOT-0014", "Tiro"): "Account/managerial intermediary in the five-month versura discussion.",
        ("ATT-PILOT-0016", "Balbus"): "Potential helper if Dolabella's assigned nomina do not match expected receipts.",
        ("ATT-PILOT-0017", "Cluvian estate"): "Estate context for the coheir payment due by Kalends of Sextilis.",
        ("ATT-PILOT-0017", "Atticus as manager"): "Manager asked to clear Cicero's accounts and ensure the Cluvian/coheir payment.",
        ("ATT-PILOT-0018", "Cicero"): "Principal whose promise/set-aside failed, forcing Aurelius into high-interest borrowing.",
        ("ATT-PILOT-0018", "Montanus"): "Underlying obligation to be discharged; Aurelius' borrowing arose around Montanus' payment.",
        ("ATT-PILOT-0018", "Eros"): "Agent told to keep money set aside for the Montanus/Aurelius obligation.",
        ("ATT-PILOT-0018", "Terentia"): "Household/family account context in the same funding problem.",
        ("ATT-PILOT-0018", "Dolabella"): "Expected funding source in related Terentia/Dolabella account discussion.",
        ("ATT-PILOT-0020", "Atticus"): "Recipient/managerial adviser for the disputed Philotimus account.",
        ("ATT-PILOT-0022", "Eros Philotimi"): "Person expected to report the amount owed by Funisulanus.",
        ("ATT-PILOT-0023", "Cn. Sallustius"): "Original source of the money that Cicero says must be handled for P. Sallustius.",
        ("ATT-PILOT-0023", "Terentia"): "Household contact asked to help arrange the Sallustius payment.",
        ("ATT-PILOT-0024", "Camillus"): "Adviser/intermediary whom Atticus should consult about Terentia satisfying her creditors.",
        ("ATT-PILOT-0024", "Atticus"): "Adviser/intermediary asked to help Terentia satisfy those she owes.",
        ("ATT-PILOT-0025", "Cicero as alleged sponsor"): "Alleged surety whose responsibility is being investigated.",
        ("ATT-PILOT-0025", "Appuleius as praediator"): "Security/praediator figure in the disputed Cornificius surety matter.",
        ("ATT-PILOT-0025", "Cornificius' procurators"): "Representatives to be consulted about the alleged surety obligation.",
        ("ATT-PILOT-0026", "Tiro"): "Reported Atticus' view and acts as account intermediary for the Caerellia debt.",
        ("ATT-PILOT-0026", "Meton"): "Related account/debt party whose status affects delaying the Caerellian payment.",
        ("ATT-PILOT-0026", "Faberius"): "Related account/debt party whose status affects delaying the Caerellian payment.",
        ("ATT-PILOT-0027", "Flaminius, for whom Montanus is surety"): "Principal for whom Montanus stood surety to Plancus.",
        ("ATT-PILOT-0028", "Faberius"): "Dolabella is said to have freed himself from heavy debt through Faberius' hand.",
        ("ATT-PILOT-0029", "Eros"): "Agent who will see to the Hortensius installment on the Ides.",
        ("FAM-PILOT-0001", "Crassus"): "Seller/house-purchase context that generated Cicero's heavy debt burden.",
        ("FAM-PILOT-0003", "M. Cicero as guarantor"): "Guarantor offering his fides for security in Mescinius' matter.",
        ("FAM-PILOT-0003", "Oppia, widow of Mindius"): "Inheritance/business context for the security arrangement.",
        ("FAM-PILOT-0004", "Tiro as agent"): "Agent sent to settle Cicero's domestic accounts and satisfy Ofillius/Aurelius.",
        ("FAM-PILOT-0005", "Tiro as collection agent"): "Agent instructed to extract payment from Flamma and handle assignment/ready-money details.",
        ("FAM-PILOT-0006", "Terentia"): "Household manager/recipient asked to help satisfy the unnamed obligation.",
        ("FAM-PILOT-0006", "Tullia"): "Household recipient included in the instruction to satisfy the unnamed obligation.",
        ("FAM-PILOT-0006", "failed property sale"): "Liquidity context explaining why the unnamed obligation could not be satisfied through sale proceeds.",
        ("QFR-PILOT-0001", "Marcus Tullius Cicero as payer/intermediary"): "Payer/intermediary through whom payments to Antonius and Caepio are described.",
        ("ATT-PILOT-0031", "Camillus"): "Reports receiving Cicero's remaining items while Philotimus has not paid Cicero.",
        ("ATT-PILOT-0032", "Milo"): "Source/account category from whose goods Philotimus lists sums owed.",
        ("ATT-PILOT-0032", "Chersonese property accounts"): "Property-account category from which Philotimus lists sums owed.",
        ("ATT-PILOT-0034", "Atticus as remittance/credit manager"): "Asked to exchange/remit Asian cistophoric funds to preserve Cicero's credit.",
        ("ATT-PILOT-0035", "Atticus as manager"): "Manager asked to see how Publilius should be dealt with and satisfied.",
        ("ATT-PILOT-0036", "Atticus as manager"): "Manager asked to provide for and leave paid the Terentia/satis dato obligation.",
        ("ATT-PILOT-0037", "sponsores"): "Sponsors/sureties whom Cicero considers calling on in the disputed sum.",
        ("ATT-PILOT-0037", "procurator"): "Procedural representative whose introduction may affect the sponsors' liability.",
        ("ATT-PILOT-0037", "Atticus"): "Adviser/manager asked how to proceed more gently in the surety/procurator issue.",
    }
    if (rid, party) in specific:
        return specific[(rid, party)]
    return f"Contextual third party connected to the obligation between borrower [{borrower}] and lender [{lender}]."


def canonical_party(name: str) -> str:
    lowered = name.lower()
    if not name:
        return ""
    specific = {
        "atticus or associates seeking funds": "Atticus or associates seeking funds",
        "atticus' steward and others": "Atticus' steward and others",
        "cicero/terentia household accounts": "Cicero/Terentia household accounts",
        "eros philotimi": "Eros",
        "philotimus / terentia's freedman": "Philotimus",
        "terentia and tullia": "Terentia and Tullia",
        "terentia or party secured through terentia": "Terentia or secured party",
        "unnamed creditor known to atticus": "unnamed creditor known to Atticus",
        "unnamed payee known to terentia and tullia": "unnamed payee known to Terentia and Tullia",
    }
    if lowered in specific:
        return specific[lowered]
    if lowered == "p. varius":
        return "P. Varius"
    if lowered == "a. caninius satyrus":
        return "A. Caninius Satyrus"
    if lowered == "iunius or party represented by iunius":
        return "Iunius"
    if lowered == "pompey or pompeian cause":
        return "Pompey"
    if lowered == "appuleius as praediator":
        return "Appuleius"
    if lowered == "q. axius' son":
        return "Q. Axius' son"
    if lowered in {"axius", "q. axius"}:
        return "Q. Axius"
    if "p. sallust" in lowered:
        return "P. Sallustius"
    if "cn. sallust" in lowered:
        return "Cn. Sallustius"
    if "curius" in lowered:
        return "Curius"
    if "atticus" in lowered:
        return "Atticus"
    if "tiro" in lowered:
        return "Tiro"
    if "terentia" in lowered:
        return "Terentia"
    if "cicero" in lowered or lowered in {"m. cicero", "marcus tullius cicero"}:
        if "quintus" in lowered:
            return "Quintus Cicero"
        return "Cicero"
    if lowered == "quintus" or "quintus tullius" in lowered:
        return "Quintus Cicero"
    if "philoti" in lowered:
        return "Philotimus"
    if "oppius" in lowered:
        return "Oppius"
    if "dolabella" in lowered:
        return "Dolabella"
    if "publili" in lowered:
        return "Publilius"
    if "faberi" in lowered:
        return "Faberius"
    if "silius" in lowered:
        return "Silius"
    if "camillus" in lowered:
        return "Camillus"
    if "eros" in lowered:
        return "Eros"
    if "flaminius" in lowered:
        return "Flaminius"
    if "flamma" in lowered:
        return "Flamma / Flaminius Flamma"
    if "montanus" in lowered:
        return "L. Tullius Montanus"
    if "plancus" in lowered:
        return "Plancus"
    if "caelius" in lowered:
        return "Caelius"
    if "caesar" in lowered:
        return "Caesar"
    if "egnatius" in lowered:
        return "Egnatius"
    if "hortensius" in lowered:
        return "Hortensius"
    if "caerellia" in lowered:
        return "Caerellia"
    if "sallust" in lowered:
        return name
    if "cornific" in lowered:
        return "Cornificius"
    if "milo" in lowered:
        return "Milo"
    if "philogenes" in lowered:
        return "Philogenes"
    if "cluvian" in lowered or "coheirs" in lowered or "cohered" in lowered:
        return "Cluvian coheirs"
    return name


def graph_canonical_party(name: str) -> str:
    canonical = canonical_party(name)
    lowered = canonical.lower()
    raw_lowered = name.lower()
    if not canonical:
        return ""
    if "curius" in lowered:
        return "Curius"
    if "unspecified" in lowered or "unspecified" in raw_lowered:
        return ""
    if lowered in {
        "atticus or associates seeking funds",
        "atticus' steward and others",
        "chersonese property accounts",
        "cicero/terentia household accounts",
        "failed property sale",
        "others",
        "possible sale buyers",
        "pompeian cause",
        "potential refinancing source",
        "terentia or secured party",
        "unnamed creditors",
        "unnamed payee known to terentia and tullia",
        "unnamed creditor known to atticus",
        "unidentified lender",
        "unknown",
        "procurator",
        "sponsores",
    }:
        return ""
    if "lender unspecified" in lowered or "source unspecified" in lowered:
        return ""
    return canonical


def analysis_parties(value: str) -> list[str]:
    return [party for party in (graph_canonical_party(piece) for piece in split_parties(value)) if party]


def analysis_party_value(value: str) -> str:
    return join_parties(analysis_parties(value))


def add_label_provenance(
    rows: list[dict[str, object]],
    record: dict[str, str],
    role_type: str,
    source_field: str,
    legacy_value: str,
) -> None:
    legacy_value = legacy_value.strip()
    if not legacy_value:
        return
    analysis_value = analysis_party_value(legacy_value)
    if legacy_value == analysis_value:
        return
    if analysis_value:
        disposition = "mapped_to_actor_level_label"
        if ";" in analysis_value:
            disposition = "split_to_actor_level_labels"
    else:
        disposition = "excluded_from_final_analysis_actor_fields"
    rows.append(
        {
            "record_id": record["record_id"],
            "collection": record["collection"],
            "source_letter_id": record["source_letter_id"],
            "role_type": role_type,
            "source_field": source_field,
            "legacy_value": legacy_value,
            "analysis_value": analysis_value,
            "disposition": disposition,
        }
    )


def add_network_edge(
    rows: list[dict[str, object]],
    record: dict[str, str],
    year: str,
    episode: str,
    source_party: str,
    target_party: str,
    edge_type: str,
    role_detail: str,
) -> None:
    source_canonical = graph_canonical_party(source_party)
    target_canonical = graph_canonical_party(target_party)
    if not source_canonical or not target_canonical:
        return
    if source_canonical == target_canonical:
        return
    rows.append(
        {
            "record_id": record["record_id"],
            "collection": record["collection"],
            "source_letter_id": record["source_letter_id"],
            "year_bce": year,
            "episode_group": episode,
            "source_party": source_party,
            "source_canonical": source_canonical,
            "target_party": target_party,
            "target_canonical": target_canonical,
            "edge_type": edge_type,
            "role_detail": role_detail,
            "confidence": record["confidence"],
        }
    )


def party_category(value: str) -> str:
    lowered = value.lower()
    if not value:
        return "unspecified"
    if "cicero" in lowered and "quintus" not in lowered:
        return "Cicero"
    if "quintus" in lowered:
        return "family"
    if "philoti" in lowered or "eros" in lowered or "flamma" in lowered or "philogenes" in lowered:
        return "freedman/agent/account"
    if "terentia" in lowered or "tiro" in lowered:
        return "household/family"
    if "coheirs" in lowered or "estate" in lowered:
        return "estate/account"
    if "unspecified" in lowered or "unknown" in lowered:
        return "unspecified"
    return "elite associate/other"


def analysis_loan_type(row: dict[str, str]) -> str:
    loan_type = row["loan_type"]
    lowered = " ".join(
        [
            row["loan_type"],
            row["interest_or_terms"],
            row["latin_evidence"],
            row["english_evidence"],
            row["interpretive_note"],
        ]
    ).lower()
    if "versura" in lowered or "refinancing" in lowered:
        return "refinancing/versura"
    if "surety" in lowered or "guarantee" in lowered:
        return "surety/guarantee"
    if "account" in lowered or "nomina" in lowered or "nomen" in lowered:
        return "account/nomina claim"
    if "credit arrangement" in lowered:
        return "credit arrangement"
    if "debt repayment" in lowered:
        return "debt repayment"
    if "personal loan" in lowered:
        return "personal loan"
    return loan_type or "unspecified"


def normalized_amount(row: dict[str, str]) -> tuple[str, str, str]:
    explicit_hs_by_record = {
        "ATT-PILOT-0012": ("600000", "explicit_roman_hs"),
        "ATT-PILOT-0023": ("30000", "explicit_roman_hs"),
        "ATT-PILOT-0027": ("20000", "explicit_roman_hs"),
        "ATT-PILOT-0031": ("20600000", "visual_loeb_page_reviewed"),
        "FAM-PILOT-0001": ("3500000", "explicit_roman_hs"),
        "ATT-PILOT-0034": ("2200000", "explicit_sestertium_phrase"),
        "VRB-STAGED-0045": ("400000", "explicit_roman_hs"),
        "VRB-STAGED-0055": ("8000000", "explicit_sestertium_phrase"),
        "VRB-STAGED-0072": ("100000", "explicit_roman_hs"),
        "VRB-STAGED-0096": ("1000000", "explicit_sestertium_phrase"),
        "VRB-STAGED-0097": ("12000000", "explicit_sestertium_phrase"),
        "VRB-STAGED-0102": ("15000000", "explicit_sestertium_phrase"),
    }
    if row["record_id"] in explicit_hs_by_record:
        normalized, certainty = explicit_hs_by_record[row["record_id"]]
        return normalized, certainty, "no"

    amount = row["amount"].strip()
    currency = row["currency_or_unit"].lower()
    if not amount:
        return "", "none", "no"
    if currency == "hs" and amount.isdigit():
        return amount, "explicit_numeric_hs", "no"
    return "", "requires_review", "yes"


def cicero_role(row: dict[str, str]) -> str:
    roles = []
    if canonical_party(row["borrower"]) == "Cicero":
        roles.append("borrower")
    if canonical_party(row["lender"]) == "Cicero":
        roles.append("lender")
    if any(canonical_party(p) == "Cicero" for p in split_parties(row["third_parties"])):
        roles.append("third_party")
    if canonical_party(row["sender"]) == "Cicero":
        roles.append("sender")
    if canonical_party(row["recipient"]) == "Cicero":
        roles.append("recipient")
    return "; ".join(dict.fromkeys(roles))


def atticus_role(row: dict[str, str]) -> str:
    roles = []
    if canonical_party(row["borrower"]) == "Atticus":
        roles.append("borrower")
    if canonical_party(row["lender"]) == "Atticus":
        roles.append("lender")
    if any(canonical_party(p) == "Atticus" for p in split_parties(row["third_parties"])):
        roles.append("third_party/manager")
    if canonical_party(row["sender"]) == "Atticus":
        roles.append("sender")
    if canonical_party(row["recipient"]) == "Atticus":
        roles.append("recipient")
    return "; ".join(dict.fromkeys(roles))


def episode_group(row: dict[str, str]) -> str:
    text = " ".join(
        row[field]
        for field in [
            "record_id",
            "source_letter_id",
            "borrower",
            "lender",
            "third_parties",
            "interest_or_terms",
            "latin_evidence",
            "interpretive_note",
        ]
    ).lower()
    if "philoti" in text or "philogenes" in text:
        return "Philotimus/Philogenes accounts"
    if "dolabella" in text:
        return "Dolabella debt/account thread"
    if "cluvian" in text or "publili" in text or "satis dato" in text:
        return "Att. 16.6 Cluvian-Publilius-Terentia cluster"
    if "silius" in text or "faberi" in text or "garden" in text or "hortis" in text:
        return "Silius/Faberius garden-finance thread"
    if "quintus" in text or "q fr." in text:
        return "Quintus debt thread"
    if "tiro" in text or "ofillius" in text or "aurelius" in text or "flamma" in text:
        return "Tiro/domestic accounts"
    if "montan" in text or "flamini" in text or "plancus" in text:
        return "Montanus/Flaminius surety thread"
    if "caelius" in text or "caesar" in text:
        return "Caelius/Caesar obligation"
    if "caerellia" in text:
        return "Caerellia account"
    if "cornific" in text:
        return "Cornificius surety"
    if "sallust" in text:
        return "Sallustius settlement"
    return "Other/private credit"


def party_summary(row: dict[str, str]) -> str:
    third = split_parties(row["third_parties"])
    third_text = ", ".join(third) if third else "none"
    return f"borrower={row['borrower']}; lender={row['lender']}; third_parties={third_text}"


def third_party_involvement(row: dict[str, str], third_parties: list[str]) -> tuple[str, str]:
    if not third_parties:
        return "", ""
    involvement_types = []
    summaries = []
    for party in third_parties:
        involvement = involvement_type_for(party, row)
        involvement_types.append(involvement)
        summaries.append(f"{party}: {involvement_summary_for(party, row)}")
    return "; ".join(dict.fromkeys(involvement_types)), " | ".join(summaries)


def add_party_role(
    rows: list[dict[str, object]],
    record: dict[str, str],
    year: str,
    episode: str,
    role_type: str,
    party_name: str,
    raw_value: str,
    is_direct: bool,
    is_third: bool,
) -> None:
    party_name = party_name.strip()
    if not party_name:
        return
    role_detail = ""
    if " as " in party_name:
        role_detail = party_name.split(" as ", 1)[1]
    canonical = canonical_party(party_name)
    if role_type in {"borrower", "lender", "third_party"}:
        canonical = graph_canonical_party(party_name)
        if not canonical:
            return
        party_name = canonical
    rows.append(
        {
            "record_id": record["record_id"],
            "collection": record["collection"],
            "source_letter_id": record["source_letter_id"],
            "year_bce": year,
            "episode_group": episode,
            "role_type": role_type,
            "party_name": party_name,
            "canonical_party": canonical,
            "role_detail": role_detail,
            "raw_value": raw_value,
            "is_direct_party": "yes" if is_direct else "no",
            "is_third_party": "yes" if is_third else "no",
            "confidence": record["confidence"],
        }
    )


def count_summary(rows: list[dict[str, object]], field: str) -> list[dict[str, object]]:
    counts = Counter(row[field] or "(blank)" for row in rows)
    return [{field: key, "record_count": value} for key, value in counts.most_common()]


def amount_profile_by_type(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "record_count": 0,
            "amount_present_count": 0,
            "normalized_values": [],
            "amount_review_needed_count": 0,
            "no_amount_count": 0,
        }
    )
    for row in rows:
        key = str(row["analysis_loan_type"] or "(blank)")
        grouped[key]["record_count"] = int(grouped[key]["record_count"]) + 1
        if row["amount_present"] == "yes":
            grouped[key]["amount_present_count"] = int(grouped[key]["amount_present_count"]) + 1
        else:
            grouped[key]["no_amount_count"] = int(grouped[key]["no_amount_count"]) + 1
        if row["amount_review_needed"] == "yes":
            grouped[key]["amount_review_needed_count"] = int(grouped[key]["amount_review_needed_count"]) + 1
        normalized = str(row["normalized_amount_hs"]).strip()
        if normalized:
            grouped[key]["normalized_values"].append(int(normalized))

    output = []
    for key, values in grouped.items():
        normalized_values = list(values["normalized_values"])
        note = "No normalized amount-bearing records."
        if normalized_values:
            note = "Totals use only conservative normalized HS/sestertius values."
        output.append(
            {
                "analysis_loan_type": key,
                "record_count": values["record_count"],
                "amount_present_count": values["amount_present_count"],
                "normalized_hs_record_count": len(normalized_values),
                "amount_review_needed_count": values["amount_review_needed_count"],
                "no_amount_count": values["no_amount_count"],
                "total_normalized_amount_hs": sum(normalized_values) if normalized_values else "",
                "min_normalized_amount_hs": min(normalized_values) if normalized_values else "",
                "max_normalized_amount_hs": max(normalized_values) if normalized_values else "",
                "normalized_amount_note": note,
            }
        )
    return sorted(output, key=lambda row: (-int(row["record_count"]), row["analysis_loan_type"]))


def timeline_by_type_and_confidence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "record_count": 0,
            "amount_present_count": 0,
            "normalized_hs_record_count": 0,
            "amount_review_needed_count": 0,
        }
    )
    for row in rows:
        key = (
            str(row["year_bce"] or "(blank)"),
            str(row["decade_bce"] or "(blank)"),
            str(row["analysis_loan_type"] or "(blank)"),
            str(row["confidence"] or "(blank)"),
        )
        grouped[key]["record_count"] += 1
        if row["amount_present"] == "yes":
            grouped[key]["amount_present_count"] += 1
        if str(row["normalized_amount_hs"]).strip():
            grouped[key]["normalized_hs_record_count"] += 1
        if row["amount_review_needed"] == "yes":
            grouped[key]["amount_review_needed_count"] += 1

    def sort_year(value: str) -> int:
        return 9999 if value == "(blank)" else -int(value)

    output = []
    for (year, decade, loan_type, confidence), values in grouped.items():
        output.append(
            {
                "year_bce": year,
                "decade_bce": decade,
                "analysis_loan_type": loan_type,
                "confidence": confidence,
                **values,
            }
        )
    return sorted(output, key=lambda row: (sort_year(row["year_bce"]), row["analysis_loan_type"], row["confidence"]))


def rejected_trigger_summary() -> list[dict[str, object]]:
    if not REJECTED_SOURCE.exists():
        return []
    rejected_rows = load_rows(REJECTED_SOURCE)
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"count": 0, "reasons": Counter(), "collections": Counter()}
    )
    for row in rejected_rows:
        term = row["matched_term"].strip() or "(blank)"
        grouped[term]["count"] = int(grouped[term]["count"]) + 1
        reason = row["rejection_reason"].strip().split(".")[0]
        grouped[term]["reasons"].update([reason or "(blank)"])
        grouped[term]["collections"].update([row["collection"] or "(blank)"])

    output = []
    for term, values in grouped.items():
        output.append(
            {
                "matched_term": term,
                "rejected_count": values["count"],
                "top_rejection_reasons": "; ".join(
                    f"{reason} ({count})" for reason, count in values["reasons"].most_common(3)
                ),
                "policy_note": "Historical rejection reasons are provenance. Under the 2026-06-21 broad estimation policy, type/scope exclusions should be re-reviewed for Ciceronian-period financial evidence; see estimation_reconsideration_queue.csv.",
                "collections": "; ".join(
                    f"{collection} ({count})" for collection, count in values["collections"].most_common()
                ),
            }
        )
    return sorted(output, key=lambda row: (-int(row["rejected_count"]), row["matched_term"]))


def amount_review_triage(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    triage_rows = []
    for row in rows:
        if row["amount_review_needed"] != "yes":
            continue
        amount = str(row["amount"]).strip()
        currency = str(row["currency_or_unit"]).strip()
        lowered = f"{amount} {currency} {row['latin_evidence']} {row['interpretive_note']}".lower()
        triage = "descriptive_only"
        reason = "Amount wording is qualitative, generic, or does not preserve a defensible numeric value."
        if any(token in lowered for token in ["hs ", "hs x", "mina", "minae", "d_c", "x_x", "greek"]):
            triage = "normalizable_with_philological_review"
            reason = "Amount/account notation may be recoverable, but should be checked against Latin, Greek, and OCR evidence before normalization."
        if amount.lower() in {"unknown", "unspecified", "summa unspecified"} or not amount:
            triage = "currently_unknowable"
            reason = "The current accepted record preserves an obligation but not a specific amount."
        if amount.lower() in {"uncertain", "multos nummos", "plus annua"}:
            triage = "descriptive_only"
            reason = "The amount expression is historically meaningful but should not be converted to a numeric HS value."
        if row["record_id"] == "ATT-PILOT-0032":
            triage = "descriptive_only"
            reason = "Reviewed Greek mina/account entries preserve multiple account values and interest, but not a single defensible HS normalization."
        if row["record_id"] == "VRB-STAGED-0012":
            triage = "currently_unknowable"
            reason = "Amount belongs to a secondary claim not verified in the attached local Latin; do not normalize until the exact primary citation is secured."
        if row["record_id"] == "VRB-STAGED-0013":
            triage = "descriptive_only"
            reason = "Att. 1.13 supports the Messalla house-purchase amount and friends-resources language, but the centies/trecies notation and OCR display need a policy before normalization."
        if row["record_id"] == "VRB-STAGED-0084":
            triage = "descriptive_only"
            reason = "Ten-million-sesterce political-payment tradition is translation-checked but gift-versus-loan status remains unverified."
        if row["record_id"] == "VRB-STAGED-0085":
            triage = "descriptive_only"
            reason = "Ancient amount is in talents; do not convert to HS in this dataset without an explicit conversion policy."
        if row["record_id"] == "VRB-STAGED-0089":
            triage = "descriptive_only"
            reason = "Ancient amount is in talents; primary-source support is checked, but do not convert to HS without an explicit conversion policy."
        if row["record_id"] == "VRB-STAGED-0088":
            triage = "descriptive_only"
            reason = "Latin preserves multiple distinct HS figures with different roles; do not collapse them into one normalized amount."
        triage_rows.append(
            {
                "record_id": row["record_id"],
                "source_letter_id": row["source_letter_id"],
                "analysis_loan_type": row["analysis_loan_type"],
                "amount": amount,
                "currency_or_unit": currency,
                "amount_triage": triage,
                "triage_reason": reason,
            }
        )
    triage_order = {
        "normalizable_with_philological_review": 0,
        "descriptive_only": 1,
        "currently_unknowable": 2,
    }
    return sorted(triage_rows, key=lambda row: (triage_order[row["amount_triage"]], row["record_id"]))


def write_episode_memos(rows: list[dict[str, object]]) -> None:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["episode_group"] or "(blank)")].append(row)

    lines = [
        "# Cicero Loan Episode Memos",
        "",
        "Generated from `analysis/core/cicero_loans_analysis_ready.csv`.",
        "",
        "Use these memos as compact interpretive entry points. They preserve the conservative record-level evidence while treating repeated references as historical episodes.",
        "",
    ]
    for episode, episode_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        confidence_counts = Counter(str(row["confidence"]) for row in episode_rows)
        type_counts = Counter(str(row["analysis_loan_type"]) for row in episode_rows)
        status_counts = Counter(str(row["status"]) for row in episode_rows)
        normalized_values = [int(row["normalized_amount_hs"]) for row in episode_rows if str(row["normalized_amount_hs"]).strip()]
        amount_review_count = sum(1 for row in episode_rows if row["amount_review_needed"] == "yes")
        parties = Counter()
        for row in episode_rows:
            for field in ["borrower", "lender", "third_parties"]:
                parties.update(split_parties(str(row[field])))
        years = sorted({str(row["year_bce"]) for row in episode_rows if row["year_bce"]})
        record_ids = ", ".join(str(row["record_id"]) for row in episode_rows)
        lines.extend(
            [
                f"## {episode}",
                "",
                f"- Records: {len(episode_rows)} ({record_ids}).",
                f"- Years: {', '.join(years) if years else 'unparsed/undated in current analysis'}; confidence: "
                + "; ".join(f"{key}={value}" for key, value in confidence_counts.most_common())
                + ".",
                "- Obligation profile: "
                + "; ".join(f"{key}={value}" for key, value in type_counts.most_common())
                + "; status: "
                + "; ".join(f"{key}={value}" for key, value in status_counts.most_common())
                + ".",
                f"- Amount evidence: {len(normalized_values)} normalized HS row(s)"
                + (f", total {sum(normalized_values)} HS" if normalized_values else "")
                + f"; {amount_review_count} row(s) still require amount review.",
                "- Main actors: " + "; ".join(f"{key} ({value})" for key, value in parties.most_common(6)) + ".",
                "",
            ]
        )

    (SUMMARIES / "episode_memos.md").write_text("\n".join(lines), encoding="utf-8")


def write_analysis_recommendations(rows: list[dict[str, object]], amount_profile_rows: list[dict[str, object]]) -> None:
    record_count = len(rows)
    normalized_count = sum(1 for row in rows if str(row["normalized_amount_hs"]).strip())
    review_count = sum(1 for row in rows if row["amount_review_needed"] == "yes")
    third_party_count = sum(1 for row in rows if row["has_third_parties"] == "yes")
    lines = [
        "# Analysis Recommendations",
        "",
        "Generated from current analysis outputs.",
        "",
        "## Monetary And Non-Monetary Evidence",
        "",
        f"- Analyze monetary and non-monetary records together for obligation type, chronology, episodes, and party roles because the accepted corpus has only {record_count} records and many historically important rows have no defensible numeric amount.",
        f"- Keep amount-based claims separate: {normalized_count} records currently support conservative normalized HS/sestertius analysis, while {review_count} records still require amount review.",
        "- Use `summary_amounts_by_obligation_type.csv` for amount-bearing obligation types, and avoid treating blank or descriptive amounts as zero.",
        "- Use `amount_review_triage.csv` to separate potentially normalizable amount notation from descriptive-only or currently unknowable amounts.",
        "",
        "## Most Useful Next Analyses",
        "",
        f"- Treat third parties as central evidence, not metadata: {third_party_count} accepted records include at least one third party.",
        "- Interpret repeated references through episodes before making aggregate historical claims.",
        "- Use the network visualization and edge tables to distinguish direct borrower-lender relations from managerial, surety, household, and accounting context.",
        "- Use rejected-trigger summaries to document why broad Latin financial vocabulary is noisy.",
        "- Frame collection comparisons as source/survival bias: Atticus dominates the accepted corpus, so collection-level rates should not be read as direct evidence for Cicero's total credit behavior.",
        "",
        "## Amount Profile By Obligation Type",
        "",
    ]
    for row in amount_profile_rows:
        lines.append(
            f"- {row['analysis_loan_type']}: {row['record_count']} records; "
            f"{row['normalized_hs_record_count']} normalized amount row(s); "
            f"{row['amount_review_needed_count']} amount-review row(s)."
        )
    lines.append("")
    (SUMMARIES / "analysis_recommendations.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source_rows = load_rows(SOURCE)
    analysis_rows: list[dict[str, object]] = []
    party_rows: list[dict[str, object]] = []
    edge_rows: list[dict[str, object]] = []
    involvement_rows: list[dict[str, object]] = []
    label_provenance_rows: list[dict[str, object]] = []

    for row in source_rows:
        year = infer_year_bce(row["date"], row["source_letter_id"])
        episode = episode_group(row)
        amount_hs, amount_certainty, amount_review = normalized_amount(row)
        clean_row = {
            **row,
            "borrower": analysis_party_value(row["borrower"]),
            "lender": analysis_party_value(row["lender"]),
            "third_parties": analysis_party_value(row["third_parties"]),
        }
        for role_type, field in [
            ("borrower", "borrower"),
            ("lender", "lender"),
            ("third_party", "third_parties"),
        ]:
            add_label_provenance(label_provenance_rows, row, role_type, field, row[field])

        third_parties = split_parties(clean_row["third_parties"])
        borrower_parties = split_parties(clean_row["borrower"])
        lender_parties = split_parties(clean_row["lender"])
        involvement_types, involvement_summary = third_party_involvement(clean_row, third_parties)

        enriched = {
            **clean_row,
            "year_bce": year,
            "decade_bce": decade_bce(year),
            "third_party_count": len(third_parties),
            "has_third_parties": "yes" if third_parties else "no",
            "third_party_involvement_types": involvement_types,
            "third_party_involvement_summary": involvement_summary,
            "analysis_loan_type": analysis_loan_type(row),
            "amount_present": "yes" if row["amount"].strip() else "no",
            "normalized_amount_hs": amount_hs,
            "amount_certainty": amount_certainty,
            "amount_review_needed": amount_review,
            "borrower_category": party_category(clean_row["borrower"]),
            "lender_category": party_category(clean_row["lender"]),
            "cicero_role": cicero_role(clean_row),
            "atticus_role": atticus_role(clean_row),
            "episode_group": episode,
            "party_summary": party_summary(clean_row),
        }
        analysis_rows.append(clean_final_analysis_row(enriched))

        add_party_role(party_rows, clean_row, year, episode, "sender", row["sender"], row["sender"], False, False)
        add_party_role(party_rows, clean_row, year, episode, "recipient", row["recipient"], row["recipient"], False, False)
        for party in borrower_parties:
            add_party_role(party_rows, clean_row, year, episode, "borrower", party, clean_row["borrower"], True, False)
        for party in lender_parties:
            add_party_role(party_rows, clean_row, year, episode, "lender", party, clean_row["lender"], True, False)
        for party in third_parties:
            party_canonical = graph_canonical_party(party)
            add_party_role(party_rows, clean_row, year, episode, "third_party", party, clean_row["third_parties"], False, True)
            involvement_rows.append(
                clean_final_analysis_row(
                    {
                    "record_id": clean_row["record_id"],
                    "collection": clean_row["collection"],
                    "source_letter_id": clean_row["source_letter_id"],
                    "year_bce": year,
                    "episode_group": episode,
                    "third_party": party,
                    "canonical_party": party_canonical,
                    "involvement_type": involvement_type_for(party, clean_row),
                    "involvement_summary": involvement_summary_for(party, clean_row),
                    "borrower": clean_row["borrower"],
                    "lender": clean_row["lender"],
                    "loan_type": clean_row["loan_type"],
                    "status": clean_row["status"],
                    "confidence": clean_row["confidence"],
                    }
                )
            )

        for borrower in borrower_parties:
            for lender in lender_parties:
                add_network_edge(
                    edge_rows,
                    clean_row,
                    year,
                    episode,
                    borrower,
                    lender,
                    "borrower_to_lender",
                    row["loan_type"],
                )
        for third in third_parties:
            for borrower in borrower_parties:
                add_network_edge(
                    edge_rows,
                    clean_row,
                    year,
                    episode,
                    third,
                    borrower,
                    "third_party_to_borrower_context",
                    "third party connected to borrower/obligation",
                )
            for lender in lender_parties:
                add_network_edge(
                    edge_rows,
                    clean_row,
                    year,
                    episode,
                    third,
                    lender,
                    "third_party_to_lender_context",
                    "third party connected to lender/obligation",
                )

    write_rows(CORE / "cicero_loans_analysis_ready.csv", ANALYSIS_FIELDS, analysis_rows)
    write_rows(CORE / "cicero_loan_party_roles.csv", PARTY_FIELDS, party_rows)
    write_rows(CORE / "cicero_loan_network_edges.csv", EDGE_FIELDS, edge_rows)
    write_rows(CORE / "cicero_loan_third_party_involvement.csv", INVOLVEMENT_FIELDS, involvement_rows)
    write_rows(ARCHIVE / "analysis_label_provenance.csv", LABEL_PROVENANCE_FIELDS, label_provenance_rows)

    write_rows(SUMMARIES / "summary_by_collection.csv", ["collection", "record_count"], count_summary(analysis_rows, "collection"))
    write_rows(SUMMARIES / "summary_by_year.csv", ["year_bce", "record_count"], count_summary(analysis_rows, "year_bce"))
    write_rows(SUMMARIES / "summary_by_loan_type.csv", ["analysis_loan_type", "record_count"], count_summary(analysis_rows, "analysis_loan_type"))
    write_rows(SUMMARIES / "summary_by_status.csv", ["status", "record_count"], count_summary(analysis_rows, "status"))
    write_rows(SUMMARIES / "summary_by_confidence.csv", ["confidence", "record_count"], count_summary(analysis_rows, "confidence"))
    write_rows(SUMMARIES / "summary_episode_groups.csv", ["episode_group", "record_count"], count_summary(analysis_rows, "episode_group"))
    amount_profile_rows = amount_profile_by_type(analysis_rows)
    write_rows(
        SUMMARIES / "summary_amounts_by_obligation_type.csv",
        AMOUNT_PROFILE_FIELDS,
        amount_profile_rows,
    )
    write_rows(
        SUMMARIES / "summary_timeline_by_type_confidence.csv",
        TIMELINE_TYPE_FIELDS,
        timeline_by_type_and_confidence(analysis_rows),
    )
    write_rows(
        SUMMARIES / "summary_rejected_trigger_terms.csv",
        REJECTED_TRIGGER_FIELDS,
        rejected_trigger_summary(),
    )
    write_episode_memos(analysis_rows)
    write_analysis_recommendations(analysis_rows, amount_profile_rows)

    party_counts = Counter(row["canonical_party"] for row in party_rows if row["canonical_party"])
    third_party_counts = Counter(
        row["canonical_party"]
        for row in party_rows
        if row["is_third_party"] == "yes" and row["canonical_party"]
    )
    direct_counts = Counter(
        row["canonical_party"]
        for row in party_rows
        if row["is_direct_party"] == "yes" and row["canonical_party"]
    )
    financial_counts = Counter(
        row["canonical_party"]
        for row in party_rows
        if row["role_type"] in {"borrower", "lender", "third_party"} and row["canonical_party"]
    )
    top_party_rows = []
    for party, count in party_counts.most_common():
        top_party_rows.append(
            {
                "canonical_party": party,
                "all_role_count": count,
                "direct_party_count": direct_counts[party],
                "third_party_count": third_party_counts[party],
            }
        )
    write_rows(
        SUMMARIES / "summary_top_parties.csv",
        ["canonical_party", "all_role_count", "direct_party_count", "third_party_count"],
        top_party_rows,
    )
    top_financial_rows = []
    for party, count in financial_counts.most_common():
        top_financial_rows.append(
            {
                "canonical_party": party,
                "financial_role_count": count,
                "direct_party_count": direct_counts[party],
                "third_party_count": third_party_counts[party],
            }
        )
    write_rows(
        SUMMARIES / "summary_top_financial_parties.csv",
        ["canonical_party", "financial_role_count", "direct_party_count", "third_party_count"],
        top_financial_rows,
    )
    top_third_party_rows = []
    for party, count in third_party_counts.most_common():
        role_details = sorted(
            {
                row["role_detail"]
                for row in party_rows
                if row["canonical_party"] == party
                and row["is_third_party"] == "yes"
                and row["role_detail"]
            }
        )
        top_third_party_rows.append(
            {
                "canonical_party": party,
                "third_party_count": count,
                "role_details": "; ".join(role_details),
            }
        )
    write_rows(
        SUMMARIES / "summary_top_third_parties.csv",
        ["canonical_party", "third_party_count", "role_details"],
        top_third_party_rows,
    )

    amount_queue = [
        row
        for row in analysis_rows
        if row["amount_review_needed"] == "yes"
    ]
    write_rows(AUDITS / "amount_review_queue.csv", ANALYSIS_FIELDS, amount_queue)
    write_rows(AUDITS / "amount_review_triage.csv", AMOUNT_TRIAGE_FIELDS, amount_review_triage(analysis_rows))

    print(f"analysis_ready_rows={len(analysis_rows)}")
    print(f"party_role_rows={len(party_rows)}")
    print(f"network_edge_rows={len(edge_rows)}")
    print(f"third_party_involvement_rows={len(involvement_rows)}")
    print(f"amount_review_rows={len(amount_queue)}")
    print(f"third_party_records={sum(1 for row in analysis_rows if row['has_third_parties'] == 'yes')}")


if __name__ == "__main__":
    main()
