"""Unit tests for the authored-spec normalization schema tools (`just_dna_format.normalize`).

These are pure, dependency-light helpers (the format owns the reference implementation of the
consumer-side strip + the future SemVer coercion), so they are tested here in the schema package,
independent of the compiler. Wiring into `validate_spec`/`compile_module` is covered by
`compiler/tests/test_authority_keys.py`.
"""

from decimal import Decimal

from just_dna_format.normalize import (
    IDENTITY_AUTHORITY_KEYS,
    IDENTITY_AUTHORITY_REASONS,
    normalize_version,
    parse_p_value,
    strip_authority_keys,
)


def test_identity_authority_set_excludes_version() -> None:
    # version is a genuine authored field now, not something to strip.
    assert IDENTITY_AUTHORITY_KEYS == frozenset({"namespace", "owner", "canonical_id"})
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
