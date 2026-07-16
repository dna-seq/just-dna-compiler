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
  enforced `version` validator in 0.5 (see docs/PROPOSAL_0_5.md).

Dependency-light (stdlib only), like `vocab` — it is a leaf usable by any consumer without the
compiler.
"""

import re
from typing import Iterable, Mapping

# ── Registry/authority-owned identity keys (inject-only) ────────────────────────────────────────
# Identity keys the format *knows about* (they map onto `manifest.Identity` / `manifest.owner`) but
# that a module author must not set — they are stamped by whatever authority publishes the module
# (a marketplace/registry), which overrides any authored value. This constant is a documented
# CONVENIENCE a consumer may inject into `strip_authority_keys` / `validate_spec`; the format applies
# NOTHING by default, so a bare `validate_spec` still rejects a stray `namespace:`/`owner:` via
# `extra="forbid"`. Deliberately NOT the reserved namespace (`vocab.RESERVED_NAMES_0_4`): that set is
# for names expected to become future *module columns* — the opposite of these, which will never be
# authored. And `version` is deliberately ABSENT: it is a genuine (advisory) authored field now, not
# something to strip. See CONSTITUTION P2/P5 and docs/PROPOSAL_0_4_1.md.
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


def normalize_version(raw: str) -> str:
    """Coerce an informal version string to SemVer `MAJOR.MINOR.PATCH`.

    Algorithm: strip every character that is not a digit or a `.` separator, split on `.`, take the
    first three fields (empty or absent fields become `0`, leading zeros are dropped), right-padding
    with `0` to three parts. So `v2` → `2.0.0`, `3` → `3.0.0`, `1.5` → `1.5.0`, `1.2.3` → `1.2.3`
    (idempotent), `v1.2.3-beta` → `1.2.3`, and a value with no digits → `0.0.0`.

    Built now but used **read-only** in 0.4.1 — `validate_spec` calls it only to *preview* what a
    future release will read from an authored `module.version`, warning when the coerced form differs
    from the input. It becomes the enforced `version` validator in 0.5 (docs/PROPOSAL_0_5.md)."""
    cleaned = _VERSION_NOISE.sub("", raw)
    nums: list[str] = []
    for part in cleaned.split("."):
        if len(nums) == 3:
            break
        nums.append(str(int(part)) if part else "0")
    while len(nums) < 3:
        nums.append("0")
    return ".".join(nums)
