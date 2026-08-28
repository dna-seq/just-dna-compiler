"""`PUBMIND_TERMS`, and what a module carrying PubMind values actually does at compile (RM134 § A).

The one entry in `licensing.py` whose every axis is `None`, and the nulls are load-bearing:
`licensing.py` defines null as *"the terms could not be established"*, which is weaker and more
honest than either permission or refusal. The ANNOVAR-distributed table publishes no data terms, the
software licence covers the software, and the paper is CC BY-NC-ND.

**The design brief for this unit asked for a test that stripping `declared_use` makes the compile
refuse. It does not, and that is the correct behaviour rather than a gap.** `taints_commercial_use`
requires `commercial_use is False`; an *unknown* does not taint, because "we could not read the
terms" is not a finding that they forbid anything (`@no-named-licence`). So the module compiles, and
what it records instead is the honest thing: `pubmind` lands in `unknown_terms_sources` and the
module-wide `commercial_use` verdict collapses to `None` — undetermined, never permitted. The tests
below pin that, and pin the contrast against a source that really does forbid sale, so a later change
making unknown terms gate cannot land silently.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.licensing import (
    PHARMVAR_TERMS,
    PUBMIND_TERMS,
    TERMS_BY_SOURCE,
    check_declared_use,
    merge_sources_file,
)
from just_dna_format.sources import taints_commercial_use, taints_redistribution
from just_dna_format.vocab import VALID_DECLARED_USE

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def _spec_with_pubmind(tmp_path: Path, *, declared_use: str = "non_commercial") -> Path:
    """A real reference module with one annotation-layer `pubmind` row appended to `sources.csv`."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    # Through the real writer rather than by hand: it is the one that resolves the sidecar's name and
    # quotes the cells, and a hand-rolled append is how a `notice` containing a comma shifts a column.
    merge_sources_file(
        [PUBMIND_TERMS.row("annotation", declared_use=declared_use)],
        spec,
        error=RuntimeError,
    )
    return spec


def test_every_licence_axis_is_null_because_none_of_them_could_be_established() -> None:
    """`None` is not `False`: the three axes record an absence of finding, not a prohibition."""
    assert PUBMIND_TERMS.source == "pubmind"
    assert PUBMIND_TERMS.license is None
    assert PUBMIND_TERMS.share_alike is None
    assert PUBMIND_TERMS.commercial_use is None
    assert PUBMIND_TERMS.redistribution is None
    # What *is* establishable is recorded, so the nulls read as "we looked" rather than "we did not".
    assert PUBMIND_TERMS.license_url and PUBMIND_TERMS.attribution and PUBMIND_TERMS.notice
    assert TERMS_BY_SOURCE["pubmind"] is PUBMIND_TERMS


def test_a_pubmind_row_taints_nothing_because_unknown_is_not_forbidden() -> None:
    """The predicate both the compile gate and the manifest summary share, asserted directly.

    Contrasted against PharmVar, which really does forbid sale — otherwise a change flipping the
    predicate to treat `None` as `False` would pass a PubMind-only assertion.
    """
    row = PUBMIND_TERMS.row("annotation", declared_use="unstated")
    assert taints_commercial_use(row) is False
    assert taints_redistribution(row) is False
    forbidding = PHARMVAR_TERMS.row("annotation", declared_use="unstated")
    assert taints_commercial_use(forbidding) is True


def test_the_acquisition_gate_skips_rather_than_refusing_or_permitting() -> None:
    """Three outcomes, and PubMind is the middle one whatever the caller declares.

    That is why `pubmind build` carries no `--use` flag: a gate that answers the same way for every
    declaration would refuse every build, and a flag feeding it would be a flag that does nothing.
    """
    # Walked from the vocabulary, never restated: a fourth `declared_use` member added upstream must
    # be exercised here, because the "no `--use` flag" decision rests on EVERY declaration answering
    # the same way. A hand-kept tuple silently exempts the new member from the claim.
    reasons = {
        declared: check_declared_use(PUBMIND_TERMS, declared) for declared in VALID_DECLARED_USE
    }
    assert set(reasons) == set(VALID_DECLARED_USE)
    assert all(isinstance(r, str) for r in reasons.values()), reasons
    assert all("terms could not be established" in r for r in reasons.values())


@pytest.mark.parametrize("declared_use", ["non_commercial", "unstated"])
def test_a_module_carrying_pubmind_compiles_under_any_declaration(
    tmp_path: Path, declared_use: str
) -> None:
    """Unknown terms warn, they never gate — including with the declaration stripped to `unstated`.

    The parametrisation is the "strip `declared_use`" case the brief asked for, asserting what the
    code actually does. A source whose terms *are* known to forbid sale refuses here; PubMind's are
    not known, so it does not, and pretending otherwise would make the compiler assert a prohibition
    nobody published.
    """
    spec = _spec_with_pubmind(tmp_path, declared_use=declared_use)
    result = compile_module(spec, tmp_path / f"art-{declared_use}", strict=False)
    assert result.success, result.errors
    assert not [e for e in result.errors if "licensing:" in e]


def test_the_manifest_records_pubmind_as_undetermined_rather_than_permitted(tmp_path: Path) -> None:
    """The honest record: named in `unknown_terms_sources`, and the module-wide verdict is `None`.

    `True` would be the dangerous answer and `False` would be a prohibition nobody stated. A consumer
    reading `commercial_use is None` learns the question is open, which is the state we are in.
    """
    spec = _spec_with_pubmind(tmp_path)
    result = compile_module(spec, tmp_path / "art", strict=False)
    assert result.success, result.errors
    sources = result.manifest.sources
    assert sources is not None
    assert "pubmind" in sources.sources
    assert "pubmind" in sources.unknown_terms_sources
    assert sources.commercial_use is None
    assert sources.redistribution is None
    assert "annotation" not in sources.noncommercial_layers
