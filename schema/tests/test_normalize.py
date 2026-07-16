"""Unit tests for the authored-spec normalization schema tools (`just_dna_format.normalize`).

These are pure, dependency-light helpers (the format owns the reference implementation of the
consumer-side strip + the future SemVer coercion), so they are tested here in the schema package,
independent of the compiler. Wiring into `validate_spec`/`compile_module` is covered by
`compiler/tests/test_authority_keys.py`.
"""

from just_dna_format.normalize import (
    IDENTITY_AUTHORITY_KEYS,
    IDENTITY_AUTHORITY_REASONS,
    normalize_version,
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
