# Contributing Evidence and Corrections

## Fork-first workflow

1. Fork the repository and create a branch.
2. Add a proposal JSON file under `data/contributions/proposals/`.
3. Do not edit `data/canonical/`, official exposure authorities, or official results for an ordinary evidence contribution.
4. Run `make validate-proposals`, `make preview`, and `make test`.
5. Open a pull request and explain the source, interpretation, and relationship to existing records.

Supported proposal types are `new_record`, `record_correction`, `additional_source`, `actor_identity_correction`, `exposure_group_suggestion`, and `amount_normalization_correction`.

## Review and promotion

A valid proposal is not automatically canonical. Maintainers must verify its source, decide whether it is new or duplicative evidence, record the adjudication under `data/decisions/`, and update the reviewed exposure decision where required. A promoted record cannot enter an official release until:

- its canonical ID is unique;
- its source and review status are complete;
- the canonical-to-exposure mapping reconciles one-to-one;
- any amount normalization is documented;
- O5/O5-6 eligibility is explicitly reviewed; and
- the full O1-O6 rebuild and verification pass.

## Protected paths

Changes to `data/canonical/`, `data/exposure_groups/`, `config/`, `results/official/`, and `validation/` require maintainer review. Contributors may change anything in their own forks, but pull requests that bypass the proposal process will not be treated as canonical data contributions.

## Stable IDs

Proposal IDs are UUIDs and remain distinct from canonical record IDs. Accepted and rejected decisions preserve a crosswalk so provenance remains visible even when several proposals concern one canonical record.
