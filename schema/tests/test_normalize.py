"""Unit tests for the authored-spec normalization schema tools (`just_dna_format.normalize`).

These are pure, dependency-light helpers (the format owns the reference implementation of the
consumer-side strip + the future SemVer coercion), so they are tested here in the schema package,
independent of the compiler. Wiring into `validate_spec`/`compile_module` is covered by
`compiler/tests/test_authority_keys.py`.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.normalize import (
    IDENTITY_AUTHORITY_KEYS,
    IDENTITY_AUTHORITY_REASONS,
    PRESENTATION_AUTHORITY_KEYS,
    PRESENTATION_AUTHORITY_REASONS,
    SHORT_DESCRIPTION_MAX_CHARS,
    normalize_utc_timestamp,
    normalize_version,
    now_utc_iso,
    parse_p_value,
    strip_authority_keys,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import ModuleInfo
from pydantic import ValidationError


def test_identity_authority_set_excludes_version() -> None:
    # version is a genuine authored field now, not something to strip.
    assert frozenset({"namespace", "owner", "canonical_id"}) == IDENTITY_AUTHORITY_KEYS
    assert "version" not in IDENTITY_AUTHORITY_KEYS
    assert set(IDENTITY_AUTHORITY_REASONS) == set(IDENTITY_AUTHORITY_KEYS)


def test_strip_authority_keys_drops_only_injected() -> None:
    block = {"name": "m", "namespace": "acme", "owner": "acme", "title": "M"}
    clean, dropped = strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS)
    assert clean == {"name": "m", "title": "M"}
    assert dropped == ["namespace", "owner"]  # sorted


def test_strip_authority_keys_is_byte_preserving_when_nothing_matches() -> None:
    block = {"name": "m", "title": "M", "color": "#fff"}
    clean, dropped = strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS)
    assert dropped == []
    # equal dict, same insertion order -> re-serializes identically
    assert clean == block
    assert list(clean) == list(block)


def test_strip_authority_keys_preserves_order_and_is_idempotent() -> None:
    block = {"namespace": "a", "name": "m", "owner": "a", "title": "M"}
    clean, dropped = strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS)
    assert list(clean) == ["name", "title"]  # surviving keys keep their order
    again, dropped2 = strip_authority_keys(clean, IDENTITY_AUTHORITY_KEYS)
    assert again == clean and dropped2 == []


def test_strip_authority_keys_accepts_a_custom_injected_set() -> None:
    # inject-only: the caller decides the set, not the format.
    block = {"name": "m", "vendor": "x", "title": "M"}
    clean, dropped = strip_authority_keys(block, {"vendor"})
    assert clean == {"name": "m", "title": "M"} and dropped == ["vendor"]


# ── the presentation family: a second registry-owned set, one stripper (RM133) ───────────────────


def test_the_two_registry_owned_families_are_separate_and_each_key_carries_a_reason() -> None:
    """Ownership and presentation are different reasons for a key to be registry-owned.

    Separate sets rather than one merged constant is what leaves the choice of *which* family to strip
    with the caller, which is the inject-only rule this module exists to implement. Both assertions
    are equalities over the walked sets, so a key added to either without a reason fails here rather
    than reaching a consumer as an unexplained strip."""
    assert not (IDENTITY_AUTHORITY_KEYS & PRESENTATION_AUTHORITY_KEYS), "a key belongs to one family"
    assert set(PRESENTATION_AUTHORITY_REASONS) == set(PRESENTATION_AUTHORITY_KEYS)
    assert set(IDENTITY_AUTHORITY_REASONS) == set(IDENTITY_AUTHORITY_KEYS)
    assert all(reason.strip() for reason in PRESENTATION_AUTHORITY_REASONS.values())
    # `version` is a genuine advisory authored field and is in NEITHER family.
    assert "version" not in IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS


def test_one_function_strips_both_families_and_drops_exactly_their_union() -> None:
    """One path rather than two: the same stripper takes the union, and drops all of it and no more.

    The expectation is computed from the two constants at runtime, so this is an equality over the
    walked union — a new member of either family is covered the moment it is declared, and a stripper
    that silently stopped reaching one family fails."""
    both = IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS
    authored = {"name": "m", "title": "M", "description": "About m.", "report_title": "M"}
    block = authored | {key: f"registry-{key}" for key in sorted(both)}

    clean, dropped = strip_authority_keys(block, both)

    assert dropped == sorted(both)
    assert clean == authored
    assert list(clean) == list(authored), "the surviving keys keep their authored order"


def test_either_family_can_be_injected_without_the_other() -> None:
    """The point of two sets: a consumer that stamps identity but not presentation, or the reverse."""
    block = {"name": "m", "namespace": "acme", "short_description": "A short one."}

    identity_only, dropped_identity = strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS)
    assert dropped_identity == ["namespace"]
    assert "short_description" in identity_only, "presentation was not injected, so it is not stripped"

    presentation_only, dropped_presentation = strip_authority_keys(block, PRESENTATION_AUTHORITY_KEYS)
    assert dropped_presentation == ["short_description"]
    assert "namespace" in presentation_only


def test_a_block_carrying_neither_family_is_untouched_by_the_union() -> None:
    """Absent the keys, everything behaves exactly as it did before — nothing is added or reordered."""
    block = _module_block(version="v2")
    clean, dropped = strip_authority_keys(
        block, IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS
    )
    assert dropped == []
    assert clean == block and list(clean) == list(block)
    assert ModuleInfo(**clean).version == "2.0.0"


def test_short_description_is_registry_owned_and_deliberately_not_a_module_info_field() -> None:
    """The rejected repair, made falsifiable.

    Putting `short_description` on `ModuleInfo` (or on the `Display` base it extends) is the natural-
    looking route and it reproduces the defect: every key in `module_spec.yaml` is inside the bytes
    `manifest.inputs` hashes and the closure binds, so an authored subtitle would be exactly as
    un-amendable as `description` is today. It lives beside the module instead."""
    assert "short_description" in PRESENTATION_AUTHORITY_KEYS
    assert "short_description" not in ModuleInfo.model_fields
    # An author who writes it anyway is still refused — the validator stays strict, and a stripper the
    # caller did not point at it is exactly the case `extra="forbid"` is there to catch.
    with pytest.raises(ValidationError):
        ModuleInfo(**_module_block(short_description="A short one."))


def test_the_subtitle_ceiling_is_published_and_refuses_nothing() -> None:
    """The calibration ships as a constant rather than being guessed at downstream — and it is advisory.

    ~120 characters, against a measured 71 (comfortable in a card) and 467 (the subtitle that prompted
    the item). It bounds a registry-held value, which is the one place such a bound is legitimate; it
    is emphatically not a length check on the authored `description`, where a ceiling would refuse a
    merely verbose spec after its prose was written."""
    assert SHORT_DESCRIPTION_MAX_CHARS == 120
    assert 71 < SHORT_DESCRIPTION_MAX_CHARS < 467, "between the comfortable case and the outlier"
    # It is stated where a consumer stripping the key will read it.
    assert str(SHORT_DESCRIPTION_MAX_CHARS) in PRESENTATION_AUTHORITY_REASONS["short_description"]
    # Nothing in the authored surface enforces it: the 467-character case still validates untouched.
    outlier = "x" * 467
    assert ModuleInfo(**_module_block(description=outlier)).description == outlier


# ── reject_authority_keys: the diagnosis half of the same constant ──────────────────────────────


def _module_block(**extra: object) -> dict[str, object]:
    """A minimal-but-complete `module:` block, so a failure can only come from `extra`."""
    return {
        "name": "s1_probe",
        "title": "Probe",
        "description": "A probe module.",
        "report_title": "Probe",
    } | extra


def test_module_block_is_valid_without_authority_keys() -> None:
    # The guard must not fire on a clean block — otherwise every module fails.
    assert ModuleInfo(**_module_block()).name == "s1_probe"


@pytest.mark.parametrize("key", sorted(IDENTITY_AUTHORITY_KEYS))
def test_each_authority_key_fails_with_its_own_reason(key: str) -> None:
    """Every member of the set earns a diagnosis, and it is the reason the constant records.

    Parametrized over the set itself rather than a hand-written list, so a key added to
    `IDENTITY_AUTHORITY_KEYS` without a message is a failure here rather than a silent generic
    rejection."""
    with pytest.raises(ValidationError) as exc:
        ModuleInfo(**_module_block(**{key: "acme"}))
    message = str(exc.value)
    assert "registry-stamped identity key(s)" in message
    assert key in message
    assert IDENTITY_AUTHORITY_REASONS[key] in message
    # The way out is named, or the diagnosis is just a longer dead end.
    assert "strip_authority_keys" in message and "--strip-identity" in message
    # The third of the three places that say `module.version` is NOT registry-stamped — the other two
    # are the constant's own comment and `authoring_reference()`'s `registry_stamped_keys`. It is here
    # because this message is where the author who wrote a stray key is actually reading.
    assert "module.version" in message


def test_authority_keys_are_reported_together_and_sorted() -> None:
    with pytest.raises(ValidationError) as exc:
        ModuleInfo(**_module_block(namespace="acme", owner="acme", canonical_id="acme/m@1.0.0"))
    message = str(exc.value)
    # One diagnosis naming all three, in sorted order — not three separate errors.
    positions = [message.index(k) for k in ("canonical_id", "namespace", "owner")]
    assert positions == sorted(positions)


def test_an_unknown_key_still_gets_the_generic_message() -> None:
    """The guard must stay narrow: a typo is not a registry key, and saying so would misdiagnose it."""
    with pytest.raises(ValidationError) as exc:
        ModuleInfo(**_module_block(nmespace="acme"))
    message = str(exc.value)
    assert "Extra inputs are not permitted" in message
    assert "registry-stamped" not in message


def test_version_is_accepted_not_diagnosed() -> None:
    """RM17: `version` is an authored advisory field, and the whole pre-0.4 corpus carries it.

    It is the one key S1 named that must NOT reach the guard — coerced, and the pre-coercion string
    kept so a caller can report the rewrite."""
    info = ModuleInfo(**_module_block(version="v2"))
    assert info.version == "2.0.0"
    assert info.version_coerced_from == "v2"


def test_the_version_yaml_actually_hands_over_is_the_one_that_has_to_work() -> None:
    """RM17's coercion was written for `3` and could not be reached from a YAML file.

    `_enforce_semver` is `mode="after"`, so a bare `version: 3` — which YAML types as an **int** —
    was refused by the field before the coercion ran, with *Input should be a valid string*: a message
    naming the type rather than the fix. The quoted twin `'3'` coerced perfectly, and unquoted is the
    only way YAML spells a number, so the guard the pre-0.4 corpus needed was unreachable from the
    file format that corpus is written in.

    Measured before it was changed, by sweeping 61 modules from three other repositories through
    `close_module`: **26 refused on exactly this**, every one an integer, which was 90% of all
    refusals. The parametrization asserts the int and its quoted twin land on the same value, since
    "these two spellings are one version" is the actual claim.
    """
    for authored in (1, 2, 3, 5):
        from_int = ModuleInfo(**_module_block(version=authored))
        from_str = ModuleInfo(**_module_block(version=str(authored)))
        assert from_int.version == from_str.version == f"{authored}.0.0"
        assert from_int.version_coerced_from == str(authored)


def test_a_yaml_float_version_is_refused_with_the_reason_rather_than_the_type() -> None:
    """The neighbour the fix above creates, and the one case where withholding is right.

    YAML reads `1.10` as `1.1`, so an author's text is gone before any validator sees it and coercing
    would publish a version they did not write. No module in the swept corpus writes one — all 26 are
    ints — but once `version: 1` works, `version: 1.0` failing with a bare type name is the surprise.
    """
    with pytest.raises(ValidationError) as exc:
        ModuleInfo(**_module_block(version=1.10))
    message = str(exc.value)
    assert "read by YAML as a number" in message
    assert 'version: "1.1"' in message, "and it shows the spelling that works"


def test_stripping_first_leaves_a_valid_block() -> None:
    """The two halves compose: strip (opt-in) then validate, which is the consumer's real path."""
    block = _module_block(namespace="acme", owner="acme", canonical_id="acme/m@1.0.0", version="v2")
    clean, dropped = strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS)
    assert dropped == ["canonical_id", "namespace", "owner"]
    assert ModuleInfo(**clean).version == "2.0.0"  # `version` survives the strip


def test_normalize_version_coerces_informal_to_semver() -> None:
    assert normalize_version("v2") == "2.0.0"
    assert normalize_version("3") == "3.0.0"
    assert normalize_version("1.5") == "1.5.0"
    assert normalize_version("v1.2.3-beta") == "1.2.3"
    assert normalize_version("1.02.0") == "1.2.0"  # leading zeros dropped
    assert normalize_version("1.2.3.4") == "1.2.3"  # extra fields truncated
    assert normalize_version("unstable") == "0.0.0"  # no digits


def test_normalize_version_is_idempotent_on_clean_semver() -> None:
    for v in ("1.2.3", "0.0.0", "10.20.30"):
        assert normalize_version(v) == v
        assert normalize_version(normalize_version(v)) == v


# ── parse_p_value ───────────────────────────────────────────────────────────────────────────────


def test_parse_p_value_reads_every_spelling_a_curator_writes() -> None:
    # All five spell the same number, so all five must read as one value.
    for text in ("5e-8", "5E-8", "5 × 10^-8", "5x10-8", "0.00000005"):
        assert parse_p_value(text) == 5e-8, text


def test_parse_p_value_round_trips_the_authored_number() -> None:
    for text in ("5e-8", "7.7e-4", "0.03", "1"):
        assert parse_p_value(text) == float(Decimal(text)), text


def test_parse_p_value_returns_none_for_anything_not_a_definite_value() -> None:
    # An unreadable cell is not a disagreement — reading one would manufacture false findings.
    for text in ("<0.001", "> 0.05", "NS", "not significant", "5e-8 (adjusted)", "p=5e-8", "", "  ",
                 "0", "0.0", "1e", "e-8", "5e-8, 3e-4"):
        assert parse_p_value(text) is None, text
    assert parse_p_value(None) is None


def test_a_value_below_float_range_reads_as_indefinite_not_as_zero() -> None:
    # `p_value_num` could not hold 1e-350 either, so reporting a disagreement between the string and
    # the column would be a finding about float64 rather than about the module.
    assert parse_p_value("1e-350") is None
    assert float("1e-350") == 0.0


def test_parse_p_value_orders_by_magnitude() -> None:
    written = ["0.05", "5e-8", "1.24e-320"]
    assert sorted(written, key=parse_p_value) == sorted(written, key=lambda t: float(Decimal(t)))


# ── provenance timestamps: one spelling, enforced on load ───────────────────────────────────────


def test_now_utc_iso_is_second_resolution_and_z_suffixed() -> None:
    """The single producer. Sub-second precision is our HTTP latency, not a fact about a source, and
    it is the part most likely to differ between two runs that found identical facts."""
    stamp = now_utc_iso()
    assert stamp == normalize_utc_timestamp(stamp), "the producer must emit the canonical spelling"
    assert stamp.endswith("Z") and "." not in stamp
    assert datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").tzinfo is None  # the format carries no offset


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The two spellings that were actually in the tree: `.isoformat()` (literature.csv) and
        # `strftime` (sources.csv). Same instant, and they must land on the same string.
        ("2026-08-01T20:55:37.406184+00:00", "2026-08-01T20:55:37Z"),
        ("2026-08-01T20:55:37Z", "2026-08-01T20:55:37Z"),
        # An offset is converted rather than truncated — 22:55+02:00 *is* 20:55Z.
        ("2026-08-01T22:55:37+02:00", "2026-08-01T20:55:37Z"),
        # Naive is read as UTC, which is what the column is documented to be.
        ("2026-08-01T20:55:37", "2026-08-01T20:55:37Z"),
        ("  2026-08-01T20:55:37Z  ", "2026-08-01T20:55:37Z"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_utc_timestamp_canonicalizes(raw: str | None, expected: str | None) -> None:
    assert normalize_utc_timestamp(raw) == expected


def test_normalize_utc_timestamp_is_idempotent() -> None:
    """P7: a normalizer that shifted its own output would move a digest on every recompile."""
    once = normalize_utc_timestamp("2026-08-01T22:55:37+02:00")
    assert normalize_utc_timestamp(once) == once


def test_an_unreadable_timestamp_raises_rather_than_passing_through() -> None:
    """This column is machine-written, so an unreadable value is a producer bug or a hand-edit that
    meant something else. Passing it through would reintroduce the drift being removed here."""
    with pytest.raises(ValueError, match="not an ISO-8601 timestamp"):
        normalize_utc_timestamp("last Tuesday")


@pytest.mark.parametrize(
    "model,kwargs",
    [
        (SourceRow, {"source": "gnomad", "layer": "annotation"}),
        (LiteratureRow, {"pmid": "8696333"}),
        (ResolutionRow, {"variant_key": "rs334", "source": "cache", "status": "resolved"}),
        (
            FrequencyRow,
            {"variant_key": "rs334", "population": "global", "dataset": "gnomad_v4.1_joint",
             "source": "gnomad", "status": "resolved"},
        ),
        (
            GeneMetricsRow,
            {"gene": "HFE", "dataset": "gnomad_v4.1_constraint", "source": "gnomad",
             "status": "resolved"},
        ),
    ],
)
def test_every_model_carrying_fetched_at_canonicalizes_on_load(model: type, kwargs: dict) -> None:
    """Bound on all five, not just the two whose column reaches a parquet today.

    `sources.parquet` and `literature.parquet` are the ones inside `artifact.digest` right now, so those
    two are where a second spelling would mint a second artifact identity for one set of facts. The
    other three get it anyway: which sidecars are materialized has changed once already, and a column
    that is canonical only where it currently happens to matter is a column that drifts back.
    """
    row = model(**kwargs, fetched_at="2026-08-01T20:55:37.406184+00:00")
    assert row.fetched_at == "2026-08-01T20:55:37Z"
