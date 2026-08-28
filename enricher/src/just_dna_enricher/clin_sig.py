"""One clinical-significance normalizer, shared by every source that reports one (RM134 section A).

**Why this is a module and not a helper inside `clinvar_build`.** The three-way concordance check
this release builds toward reports agreement between two authorities by comparing their *normalized*
calls. A second hand-written map would make any drift between the two maps read as a disagreement
between ClinVar and PubMind, which is a finding about our own code wearing the costume of a finding
about the field. So there is one map, one severity order and one function, and every snapshot builder
calls it.

**It is deliberately dependency-free.** Only `VALID_CLIN_SIG` is imported, so a runtime pass can read
it without the `[dev]` polars extra the builders need — which is the whole argument for a shared home
rather than one builder importing another.

**Two defects were fixed on the way out of `clinvar_build`, and both were invisible from ClinVar's
side alone.** The map's keys are underscored because that is how ClinVar spells `CLNSIG`; PubMind
spells the same concepts with spaces. So `Uncertain significance` and `Conflicting` both fell through
to `other`, against `uncertain_significance` and `conflicting` for ClinVar's own wording of the same
two concepts — a manufactured disagreement, on the largest disagreeing class in the measured corpus
join. The repair is a whitespace→underscore step in the tokenizer, which is an identity on every key
below, plus the bare `conflicting` key PubMind's single-word token needs.

**A composite token is still resolved by severity, not by a special case.** PubMind's
`Benign/Likely benign` folds to `likely_benign`, exactly as ClinVar's `Benign/Likely_benign` does,
because that is what one normalizer means: the same concept gets the same answer whoever spelled it.
"""

import re

from just_dna_format.vocab import VALID_CLIN_SIG

# ── raw significance token → VALID_CLIN_SIG ─────────────────────────────────────────────────────
#
# ClinVar's aggregate germline classifications and PubMind's six `pathogenicity_sum` values, keyed by
# the token as it is spelled after `_tokenize` below. A token a source coins that has no module axis
# maps to `other` via the default; the raw value is always kept beside the mapped one in the snapshot
# (`clin_sig_raw`), so nothing is lost and the mapping stays auditable.
CLIN_SIG_MAP: dict[str, str] = {
    "pathogenic": "pathogenic",
    "pathogenic_low_penetrance": "pathogenic",
    "likely_pathogenic": "likely_pathogenic",
    "likely_pathogenic_low_penetrance": "likely_pathogenic",
    "uncertain_significance": "uncertain_significance",
    "uncertain_risk_allele": "uncertain_significance",
    "likely_benign": "likely_benign",
    "benign": "benign",
    "drug_response": "drug_response",
    "association": "association",
    "association_not_found": "other",
    "risk_factor": "risk_factor",
    "established_risk_allele": "risk_factor",
    "likely_risk_allele": "risk_factor",
    "protective": "protective",
    "affects": "affects",
    # PubMind's whole-token spelling of the concept ClinVar states as a sentence. It is a key rather
    # than a prefix match because a vocabulary is a set of members, not a substring test.
    "conflicting": "conflicting",
    "conflicting_classifications_of_pathogenicity": "conflicting",
    "conflicting_interpretations_of_pathogenicity": "conflicting",
    "not_provided": "not_provided",
    "no_classification_provided": "not_provided",
    "no_classification_for_the_single_variant": "not_provided",
    "no_classifications_from_unflagged_records": "not_provided",
    "no_assertion_provided": "not_provided",
    "other": "other",
    "confers_sensitivity": "other",
    "low_penetrance": "other",
}

# When a single value carries several tokens (`Pathogenic/Likely_pathogenic`,
# `Benign/Likely benign`, joined by | or / or ,), the winner is the most clinically consequential —
# picked by this explicit order, never set iteration (Principle 7: deterministic). Every member of
# VALID_CLIN_SIG appears exactly once.
CLIN_SIG_SEVERITY: tuple[str, ...] = (
    "pathogenic",
    "likely_pathogenic",
    "drug_response",
    "risk_factor",
    "affects",
    "association",
    "protective",
    "conflicting",
    "uncertain_significance",
    "likely_benign",
    "benign",
    "not_provided",
    "other",
)
assert set(CLIN_SIG_SEVERITY) == VALID_CLIN_SIG, "severity order must cover VALID_CLIN_SIG exactly"
# The map is a registry too, and its *range* is the thing a drift would break: a key mapped to a
# member this vocabulary does not have would write an unwritable cell. Equality rather than a subset,
# because a member no key reaches is a member no source can ever produce — which is a gap worth
# failing on rather than a harmless slack.
assert set(CLIN_SIG_MAP.values()) == VALID_CLIN_SIG, "the map's range must be VALID_CLIN_SIG exactly"

CLIN_SIG_SPLIT = re.compile(r"[|/,]")
_WHITESPACE = re.compile(r"\s+")


def _tokenize(raw: str) -> str:
    """One split token → its map key: lowercased, with internal whitespace folded to `_`.

    The whitespace fold is an **identity on every `CLIN_SIG_MAP` key**, all of which are already
    underscored because ClinVar underscore-encodes spaces in `CLNSIG`. It exists for the sources that
    do not — PubMind writes `Uncertain significance` — and it is a pre-step rather than a second map
    precisely so the two spellings cannot drift apart.
    """
    return _WHITESPACE.sub("_", raw.strip()).lower()


def normalize_clin_sig(raw: str | None) -> str:
    """Fold a raw clinical-significance value into a single `VALID_CLIN_SIG` member.

    Absent, empty **or whitespace-only** is `not_provided` — the source states no classification,
    which is a member of the vocabulary rather than an unknown to withhold. A token with no module
    axis becomes `other`, and the two are different answers: a source that said nothing has not
    disagreed with anybody, while one that said something we do not model has.

    A value that splits into no tokens at all (`"|||"`) reaches `not_provided` for the same reason.
    The extracted original answered `other` there, which read a blank cell as an unmodelled wording;
    no ClinVar `CLNSIG` takes that shape, so nothing built to date moves.
    """
    if not (raw or "").strip():
        return "not_provided"
    tokens = {_tokenize(tok) for tok in CLIN_SIG_SPLIT.split(raw) if tok.strip()}
    if not tokens:
        return "not_provided"
    mapped = {CLIN_SIG_MAP.get(tok, "other") for tok in tokens}
    for sig in CLIN_SIG_SEVERITY:
        if sig in mapped:
            return sig
    return "other"
