# Changelog

## 1.1.3 - 2026-07-15

- Labeling adjustments only; no substantive record content, exposure-group values, calculated values, sensitivity results, or paper findings changed.
- Rename the 95 secondary-source staged record identifiers to the `SEC-STAGED-XXXX` convention.
- Rename 68 associated worker, missing-record, delta, and supplement provenance handles to the corresponding `SEC` conventions.
- Propagate the new identifiers through reviewed authorities, derived O4-O6 outputs, provenance manifests, analysis rules, and release checksums.
- Preserve all published quantitative findings; this change affects labeling and identifier-derived hashes only.

## 1.1.2 - 2026-07-15

- Publish version 1.0 of the associated independent research working paper.
- Add the working-paper citation, version, checksum, and public PDF links.
- Update repository citation metadata for Han Chin Li and release 1.1.2.

## 1.1.1 - 2026-07-15

- Replace provisional internal workflow statuses with official release labels.
- Classify `selected_k` and `hierarchical_p50_hs` as `official_release_intermediate`.
- Classify the five published O5/O6 results as `official_release_calculation`.

## 1.1.0 - 2026-07-15

- Publish the complete paper sensitivity package and paper-facing figure rebuild.
- Add a machine-verifiable paper-to-output claim map and `make reproduce-paper-findings`.
- Expand the canonical schema to every released column and enforce required and controlled values.
- Correct public source availability metadata and document exact consulted editions.
- Expand release checksums to all reviewed inputs, official outputs, and validation artifacts.
- Document and test the fixed 12-decimal calculation-interface precision policy.

## 1.0.0 - 2026-07-14

- Published the 114-record reviewed canonical snapshot.
- Published reviewed exposure-group and actor/relation authorities.
- Added reproducible O1-O6 and O5-6 distribution calculations.
- Added fork-first proposal validation and non-canonical impact previews.
