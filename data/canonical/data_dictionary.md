# Canonical Data Dictionary

The canonical CSV preserves extraction, provenance, classification, verification, and deduplication fields. `merged_record_id` is the stable release record identifier. Blank amounts are unknown, not zero.

Important field families include:

- source identity: collection, book, letter, source citation, date, edition or URL;
- parties: borrower, lender, sender, recipient, and third parties;
- evidence: Latin text, English interpretation, and interpretive note;
- financial classification: status, loan type, amount, unit, interest, and terms;
- review: confidence, verification status, primary-source status, and review status;
- provenance: source layer, Verboven references, deduplication group, and repeated mentions.

Every released column, its required/optional status, and its controlled values are recorded in `schema.csv`. Blank amounts mean unknown or unstated, never zero. Contributors propose changes through `data/contributions/proposals/` rather than editing the canonical CSV.
