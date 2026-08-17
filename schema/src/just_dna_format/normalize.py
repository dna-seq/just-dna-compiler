"""
Authored-spec normalization schema tools — the format's *reference implementation* of two
consumer-facing pre-processing steps that sit **before** validation, never inside it.

Both exist because the authored `module:` block collides with `extra="forbid"` for keys the format
knows about but the author should not set (registry-stamped identity), and because the informal
`version` an author writes (`v2`, `3`) is not yet SemVer. The design rule (CONSTITUTION Principle 2's
inject-only *spirit*, and "a validator validates, it does not fix"): the **consumer injects** the set
of authority-owned keys it stamps; the format owns the pure, re-runnable stripper that consumes that
set. The validator itself stays strict — if a stripper is skipped or a key slips through,
`extra="forbid"` still errors loudly, pointing at exactly where expectation broke.

- `strip_authority_keys` — drop consumer/registry-owned identity keys from the `module:` block. The
  reference impl of a marketplace's own `strip_registry_owned_keys()`. Nothing is applied by default;
  a consumer opts in by passing `IDENTITY_AUTHORITY_KEYS` (or its own set).
- `normalize_version` — coerce an informal version string to SemVer `MAJOR.MINOR.PATCH`. Built now,
  used **read-only** in 0.4.1 to *preview* what a future release will read; slated to become the
  enforced `version` validator in 0.5 (see docs/proposals/PROPOSAL_0_5.md).
- `parse_p_value` — read a free-form authored `p_value` string as a number, or `None` when it does not
  denote a definite value. Same shape as the two above: a pure, total, re-runnable read of informal
  authored text, used by the compiler to cross-check the typed `p_value_num` against the string
  beside it (0.5).
- `now_utc_iso` / `normalize_utc_timestamp` — the single spelling of a provenance timestamp, and the
  canonicalizer that enforces it on load. Unlike the three above these are *not* read-only previews:
  the value lands in `sources.parquet`/`literature.parquet` and so in `artifact.digest`, where two
  spellings of one instant would be two identities for one set of facts.

Dependency-light (stdlib only), like `vocab` — it is a leaf usable by any consumer without the
compiler.
"""

import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

# ── Registry/authority-owned identity keys (inject-only) ────────────────────────────────────────
# Identity keys the format *knows about* (they map onto `manifest.Identity` / `manifest.owner`) but
# that a module author must not set — they are stamped by whatever authority publishes the module
# (a marketplace/registry), which overrides any authored value. This constant is a documented
# CONVENIENCE a consumer may inject into `strip_authority_keys` / `validate_spec`; the format applies
# NOTHING by default, so a bare `validate_spec` still rejects a stray `namespace:`/`owner:` via
# `extra="forbid"`. Deliberately NOT the reserved namespace (`vocab.RESERVED_NAMES_0_4`): that set is
# for names expected to become future *module columns* — the opposite of these, which will never be
# authored. And `version` is deliberately ABSENT: it is a genuine (advisory) authored field now, not
# something to strip. See CONSTITUTION P2/P5 and docs/proposals/PROPOSAL_0_4_1.md.
IDENTITY_AUTHORITY_KEYS: frozenset[str] = frozenset({"namespace", "owner", "canonical_id"})

# Why each authority key is not author-set — a per-key note a consumer can surface when it strips one.
IDENTITY_AUTHORITY_REASONS: dict[str, str] = {
    "namespace": "the owning account/org slug — stamped by the publishing registry on publish",
    "owner": "the owning account — stamped by the publishing registry on publish",
    "canonical_id": "namespace/name@version — derived by the publishing registry, not authored",
}

# A version part is a run of digits; parts are separated by dots. Everything else (a leading `v`, a
# `-beta` pre-release tag, stray spaces) is noise the coercion drops.
_VERSION_NOISE: re.Pattern[str] = re.compile(r"[^\d.]")

# The p-value forms a curator actually writes. Two accepted spellings of scientific notation — `5e-8`
# and the typeset `5 × 10^-8` (also `x`/`X`, with or without the caret) — plus a plain decimal. The
# match is deliberately **anchored on the whole string**: a cell like `5e-8 (adjusted)` or `p<0.001`
# is not a definite value, and half-reading it would invent a precision the author did not state.
_P_VALUE_SCIENTIFIC: re.Pattern[str] = re.compile(
    r"^([0-9]*\.?[0-9]+)\s*(?:[eE]|[×xX]\s*10\s*\^?)\s*([+-]?[0-9]+)$"
)
_P_VALUE_DECIMAL: re.Pattern[str] = re.compile(r"^[0-9]*\.?[0-9]+$")


def strip_authority_keys(
    block: Mapping[str, object], authority_keys: Iterable[str]
) -> tuple[dict[str, object], list[str]]:
    """Drop the injected authority-owned keys from a `module:` block, before validation.

    Returns `(clean, dropped)`: a shallow copy of `block` with any key in `authority_keys` removed
    (insertion order preserved), and the sorted list of names actually dropped. **Byte-preserving
    when nothing matches** — a clean block round-trips to an equal dict in the same order, so a spec
    that carries none of the injected keys is untouched. Pure and idempotent: re-running on the
    result drops nothing.

    This is the format's reference implementation of a marketplace's `strip_registry_owned_keys()`.
    It is inject-only: `authority_keys` is supplied by the caller (e.g. `IDENTITY_AUTHORITY_KEYS`),
    never hardcoded here — the format does not bake in any one consumer's identity conventions."""
    keys = frozenset(authority_keys)
    dropped = sorted(k for k in block if k in keys)
    clean = {k: v for k, v in block.items() if k not in keys}
    return clean, dropped


def reject_authority_keys(data: object) -> object:
    """A `mode="before"` guard for the authored `module:` block, layered on top of `extra="forbid"`.

    Same shape and same reason as `vocab.reject_reserved`, on the other half of the namespace:
    `extra="forbid"` already refuses `namespace:`/`owner:`/`canonical_id:`, but it refuses them with
    the generic "extra inputs are not permitted", which is a dead end for the one author most likely
    to hit it — someone carrying a pre-0.4 spec whose keys the *format's own docs* describe as
    registry-filled. This guard runs first and names the key, why it is not authored
    (`IDENTITY_AUTHORITY_REASONS`), and the two ways out.

    **It diagnoses; it does not strip.** The inject-only rule (CONSTITUTION P2's spirit) is about
    *applying* one consumer's identity convention inside the validator, which is why
    `strip_authority_keys` is opt-in and the format still applies nothing by default. A message is not
    an application: a block that reaches this guard is one no stripper was pointed at, and the whole
    value of the constant is telling that caller the stripper exists. Validity is unchanged — the
    block was invalid before this function and is invalid after it.

    A typo'd or genuinely unknown key still falls through to `extra="forbid"`'s generic message, and
    non-mapping input passes through untouched (pydantic handles it)."""
    if isinstance(data, dict):
        hits = sorted(k for k in data if k in IDENTITY_AUTHORITY_KEYS)
        if hits:
            reasons = "; ".join(f"{h!r} is {IDENTITY_AUTHORITY_REASONS[h]}" for h in hits)
            raise ValueError(
                f"registry-stamped identity key(s), not authored fields: {reasons}. Omit them from "
                f"module_spec.yaml, or have the publishing consumer strip them before validation "
                f"(just_dna_format.normalize.strip_authority_keys / IDENTITY_AUTHORITY_KEYS, "
                f"threaded as validate_spec(..., authority_keys=...) or the compiler CLI's "
                f"--strip-identity). Note `module.version` is NOT one of these: it is a genuine "
                f"advisory authored field, coerced to SemVer."
            )
    return data


def normalize_version(raw: str) -> str:
    """Coerce an informal version string to SemVer `MAJOR.MINOR.PATCH`.

    Algorithm: strip every character that is not a digit or a `.` separator, split on `.`, take the
    first three fields (empty or absent fields become `0`, leading zeros are dropped), right-padding
    with `0` to three parts. So `v2` → `2.0.0`, `3` → `3.0.0`, `1.5` → `1.5.0`, `1.2.3` → `1.2.3`
    (idempotent), `v1.2.3-beta` → `1.2.3`, and a value with no digits → `0.0.0`.

    Built now but used **read-only** in 0.4.1 — `validate_spec` calls it only to *preview* what a
    future release will read from an authored `module.version`, warning when the coerced form differs
    from the input. It becomes the enforced `version` validator in 0.5 (docs/proposals/PROPOSAL_0_5.md)."""
    cleaned = _VERSION_NOISE.sub("", raw)
    nums: list[str] = []
    for part in cleaned.split("."):
        if len(nums) == 3:
            break
        nums.append(str(int(part)) if part else "0")
    while len(nums) < 3:
        nums.append("0")
    return ".".join(nums)


def parse_p_value(raw: str | None) -> float | None:
    """Read a free-form `p_value` string as a number.

    Returns `None` whenever the string does not denote one definite value — an unreadable cell is not
    a disagreement, and treating it as one would turn every `"<0.001"`, `"NS"` or `"p = 5e-8, adj."`
    into a false finding. `None` therefore covers: absent/blank, a bound or a word rather than a
    number, trailing commentary, and an exact `0` (a p-value written as zero is the source's own
    underflow, so it is not comparable to anything).

    A value too small for a float (below ~5e-324) reads as `None` for the same reason: it underflows
    to zero here, `p_value_num` could not hold it either, and reporting "the string says 1e-350 but
    the column says nothing" would be a finding about float64 rather than about the module.

    Accepts `5e-8`, `5E-8`, `5 × 10^-8` / `5x10-8`, and plain decimals like `0.03`."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    scientific = _P_VALUE_SCIENTIFIC.match(text)
    if scientific:
        literal = f"{scientific.group(1)}E{scientific.group(2)}"
    elif _P_VALUE_DECIMAL.match(text):
        literal = text
    else:
        return None

    try:
        value = float(Decimal(literal))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return value or None


UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def now_utc_iso() -> str:
    """The one producer of a provenance timestamp: ISO-8601 UTC, second resolution, `Z`-suffixed.

    Every pass that stamps `fetched_at` calls this, because two producers of one column reliably
    disagree: `sources.csv` was written `2026-08-03T02:03:23Z` while `literature.csv` was written
    `2026-08-01T20:55:37.406184+00:00` — the same instant in two spellings, from two `datetime.now(UTC)`
    calls that differed only in whether `.isoformat()` or `strftime` was reached for.

    Second resolution rather than microsecond is deliberate. Sub-second precision says nothing true
    about when a *source* published anything — it is the latency of our own HTTP call — and it is the
    part most likely to differ between two runs that found identical facts.
    """
    return datetime.now(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def normalize_utc_timestamp(raw: str | None) -> str | None:
    """Canonicalize any ISO-8601 timestamp to `now_utc_iso()`'s spelling, or raise if it is not one.

    Applied as a `mode="before"` validator on every model carrying `fetched_at`, so the column is
    canonical *on load* rather than merely by convention at the point of writing. That matters because
    the value reaches `sources.parquet`/`literature.parquet` and therefore `artifact.digest`: two
    spellings of one instant would otherwise be two artifact identities for one set of facts.

    Offsets are converted to UTC and a naive value is *read* as UTC (the column is documented UTC).
    Sub-second precision is dropped rather than rounded — see `now_utc_iso`. A value `fromisoformat`
    cannot read raises instead of being passed through: this field is machine-written, so an unreadable
    one is a bug in a producer or a hand-edit that meant something else, and silently keeping it would
    reintroduce exactly the drift this function exists to end.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"not an ISO-8601 timestamp: {raw!r} (expected e.g. '2026-08-03T02:03:23Z')"
        ) from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime(UTC_TIMESTAMP_FORMAT)
