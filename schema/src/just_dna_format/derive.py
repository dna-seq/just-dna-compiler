"""Legacy → 0.3 column derivations (the "upgrade" back-population) and the read-time aliases that let
a consumer see the orthogonal 0.3 axes even on a 0.1/0.2 module that only set `state`.

Kept as a leaf module (it imports nothing from `spec`) so both `spec` — for its `effective_*`
accessors and `upgraded()` — and external consumers (the marketplace `revalidate`/`needs_upgrade`
flow) can import these pure functions without an import cycle.

`state` and the ClinVar booleans stay **required/authoritative** for 0.2 backward-compat
(CONSTITUTION Principle 3 forbids making a required field optional inside a major); the new axes are
optional, with these derivations as their fallback. Every function here is **total and idempotent**:
applying it to an already-derived value is a no-op (CONSTITUTION Principle 7). See the
"Upgrade derivation" section of docs/COMPILER.md.
"""


# The "Upgrade derivation" mapping (docs/COMPILER.md): legacy `state` → (direction, stat_significance).
# **Deliberately gains no `contested` entry, and the asymmetry with `_DIRECTION_TO_STATE` is correct**
# (RM150). The two maps look like they should mirror, and they do not: no legacy `state` value means
# *the sources disagree about the sign*, so there is nothing to map FROM. A module upgraded off the
# legacy column can never produce `contested`; only an author writing `direction` directly can.
_STATE_TO_DIRECTION: dict[str, str] = {
    "protective": "protective",
    "risk": "risk",
    "neutral": "neutral",
    "significant": "unknown",  # significance is not a direction; refined from weight sign below
    "alt": "unknown",
    "ref": "unknown",
}
_STATE_TO_STAT_SIGNIFICANCE: dict[str, str] = {
    "protective": "unknown",
    "risk": "unknown",
    "neutral": "unknown",
    "significant": "significant",
    "alt": "unknown",
    "ref": "unknown",
}
# The trimmed legacy set an upgraded module emits: everything without a legacy spelling collapses to
# `neutral`.
#
# **Every member of `vocab.VALID_DIRECTIONS` must have an explicit entry here, and that is a rule
# rather than a convention** (RM150). `trimmed_state` reads this with `.get(direction, "neutral")` — a
# default, not a lookup that raises — so a direction missing from this map does not fail, it silently
# projects to `neutral`. Measured before `contested` was added: `trimmed_state("contested")` already
# returned `"neutral"`, and so does `trimmed_state("total nonsense")`. Adding a member to the
# vocabulary and stopping there therefore ships a module whose `upgraded()` emits a wrong legacy
# `state` with nothing failing anywhere.
#
# That is why the guard is a **registry-iterating equality** over the walked set
# (`set(_DIRECTION_TO_STATE) == VALID_DIRECTIONS`) and not a spot check: a test asserting
# `trimmed_state("contested") == "neutral"` passes today, before the member exists, and proves
# nothing. The default stays for input that is not a direction at all.
_DIRECTION_TO_STATE: dict[str, str] = {
    "protective": "protective",
    "risk": "risk",
    "neutral": "neutral",
    "unknown": "neutral",
    # `contested` collapses to `neutral` too, and the projection is right once it is EXPLICIT: the
    # legacy set has no member meaning "the sources disagree about the sign", and `neutral` is where
    # `unknown` already lands. Lossy, like every projection into the trimmed set.
    "contested": "neutral",
}


def direction_from_state(state: str, weight: float | None = None) -> str:
    """Derive `direction` from the legacy `state` (plus the `weight` sign when informative).

    `significant` carries no direction on its own, so it is refined from the weight sign when present
    (positive → protective, negative → risk); otherwise it, and the retired `alt`/`ref` descriptors,
    map to the honest `unknown` the old enum lacked."""
    if state == "significant" and weight is not None:
        if weight > 0:
            return "protective"
        if weight < 0:
            return "risk"
    return _STATE_TO_DIRECTION.get(state, "unknown")


def stat_significance_from_state(state: str) -> str:
    """Derive `stat_significance` from the legacy `state` (only `significant` is informative)."""
    return _STATE_TO_STAT_SIGNIFICANCE.get(state, "unknown")


def trimmed_state(direction: str) -> str:
    """Project a `direction` back into the trimmed legacy `state` set {protective, risk, neutral}.

    `unknown` and `contested` both collapse to `neutral` — the legacy set has no member for either.
    This is the derived, deprecated `state` an upgraded module emits. See `_DIRECTION_TO_STATE` for
    why every vocabulary member needs an explicit entry there rather than relying on the default.
    """
    return _DIRECTION_TO_STATE.get(direction, "neutral")


def clin_sig_from_booleans(
    pathogenic: bool | None, benign: bool | None, clinvar: bool | None
) -> str | None:
    """Derive a `clin_sig` tier from the lossy legacy ClinVar booleans.

    `pathogenic` → pathogenic; `benign` → benign; in-ClinVar with neither flag →
    uncertain_significance; otherwise None (nothing to say). Lossy by construction — legacy cannot
    recover `likely_pathogenic`/`likely_benign`."""
    if pathogenic:
        return "pathogenic"
    if benign:
        return "benign"
    if clinvar:
        return "uncertain_significance"
    return None


def pathogenic_from_clin_sig(clin_sig: str | None) -> bool | None:
    """The `pathogenic` boolean implied by a `clin_sig` tier: True for the pathogenic tiers, else
    None (the tier is silent on the boolean — we never fabricate a `False` a curator did not state)."""
    if clin_sig in {"pathogenic", "likely_pathogenic"}:
        return True
    return None


def benign_from_clin_sig(clin_sig: str | None) -> bool | None:
    """The `benign` boolean implied by a `clin_sig` tier: True for the benign tiers, else None."""
    if clin_sig in {"benign", "likely_benign"}:
        return True
    return None
