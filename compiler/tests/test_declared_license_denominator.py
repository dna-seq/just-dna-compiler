"""The licence-disagreement warning names its denominator (0.7, S79).

The check compares `module_spec.yaml`'s `license:` against the annotation-layer rows in the licensing
sidecar. It filtered to the rows that *differ* and then rendered that remainder as though it were the
whole set — so a declaration matching one of two rows printed the same shape as one matching none.

Those are different problems with different repairs. *Your declaration is unsupported* means the author
picked a licence no source grants; *your declaration is not universal* is the ordinary shape of a
mixed-licence module, where the most restrictive term binds the artifact and the declaration is already
correct. An author reading the first when the second was true re-adjudicated a module's whole licence
position and found nothing wrong — reported twice, from two separate rounds.

The fixture is the reporter's own two-source `SIRT6` module: `CC-BY-NC-ND-4.0` (the binding constraint,
and what the module declares) beside `CC-BY-4.0`.
"""

from pathlib import Path

from just_dna_compiler.compiler import _check_declared_license_agrees, compile_module
from just_dna_format.sources import SourceRow

_BINDING = "CC-BY-NC-ND-4.0"
_PERMISSIVE = "CC-BY-4.0"


def _annotation(source: str, license: str) -> SourceRow:
    return SourceRow(source=source, layer="annotation", license=license)


#: The reported module: one row the declaration matches exactly, one it does not.
_MIXED = [_annotation("pmid:41249831", _BINDING), _annotation("pmid:28399814", _PERMISSIVE)]


def _one(rows: list[SourceRow], declared: str | None) -> str | None:
    found = _check_declared_license_agrees(rows, declared)
    assert len(found) <= 1
    return found[0] if found else None


# ── the two cases the old message could not tell apart ──────────────────────────────────────────


def test_a_declaration_matching_some_rows_says_so_with_a_count() -> None:
    """The defect: the agreeing row was invisible in the sentence complaining about agreement."""
    message = _one(_MIXED, _BINDING)

    assert message is not None
    assert "1 of 2 annotation-layer source(s)" in message
    # The disagreeing licence is still named — the finding is real and worth reporting.
    assert _PERMISSIVE in message
    # And the reading that cost two rounds of work is gone: nothing says the declaration is unheld.
    assert "no annotation-layer source reports it" not in message


def test_a_declaration_matching_nothing_reads_differently() -> None:
    """The discriminating half, and the reason a count alone was not enough.

    Without this the test above passes for a message that always says "N of M", which would make the
    genuinely-unsupported case *less* legible than before. The two must be distinguishable by shape,
    not only by arithmetic.
    """
    message = _one(_MIXED, "MIT")

    assert message is not None
    assert "no annotation-layer source reports it" in message
    assert _BINDING in message and _PERMISSIVE in message


def test_a_declaration_every_row_agrees_with_stays_silent() -> None:
    """Unchanged, and the property that keeps this a finding rather than a report."""
    assert _check_declared_license_agrees([_annotation("a", "MIT"), _annotation("b", "MIT")], "MIT") == []


def test_a_module_declaring_nothing_is_not_asked_the_question() -> None:
    """`None` is not a mismatch — there is no claim to contradict."""
    assert _check_declared_license_agrees(_MIXED, None) == []
    assert _check_declared_license_agrees(_MIXED, "") == []


# ── what the denominator counts ─────────────────────────────────────────────────────────────────


def test_the_denominator_counts_rows_not_distinct_licences() -> None:
    """Two sources sharing a licence are two obligations, and the author is checking against sources.

    Counting distinct licences would report "1 of 2" for a module with three rows, which is a number
    matching nothing the author can see in their own file.
    """
    rows = [
        _annotation("pmid:1", _BINDING),
        _annotation("pmid:2", _PERMISSIVE),
        _annotation("pmid:3", _PERMISSIVE),
    ]
    message = _one(rows, _BINDING)

    assert message is not None
    assert "2 of 3 annotation-layer source(s)" in message
    # One licence, named once: the list is of licences, the count is of rows, and both are honest.
    assert message.count(_PERMISSIVE) == 1


def test_a_row_with_no_licence_is_outside_the_denominator() -> None:
    """Unknown terms are neither agreement nor disagreement — the house algebra, in a count.

    A source whose licence could not be established must not inflate the denominator, or the author is
    told a source disagrees when nobody established what it says.
    """
    rows = [*_MIXED, SourceRow(source="pmid:3", layer="annotation")]
    message = _one(rows, _BINDING)

    assert message is not None
    assert "1 of 2 annotation-layer source(s)" in message


def test_a_non_annotation_layer_row_is_not_counted() -> None:
    """The check is about the annotation layer, and the denominator has to agree with the filter.

    A `resolution`-layer row cannot taint a module — that is the standing rule the orphan check's
    exemption rests on — so counting one here would make the denominator disagree with the set the
    warning is actually about.
    """
    rows = [*_MIXED, SourceRow(source="ensembl", layer="resolution", license="Apache-2.0")]
    message = _one(rows, _BINDING)

    assert message is not None
    assert "1 of 2 annotation-layer source(s)" in message
    assert "Apache-2.0" not in message


# ── the surrounding contract ────────────────────────────────────────────────────────────────────


def test_the_grepped_fragment_and_the_non_escalation_both_survive(tmp_path: Path) -> None:
    """`declares license` leads the sentence, and this still never fails a build.

    Two claims about a legal position disagreeing is not the compiler's to arbitrate — the second
    deliberate non-escalation after the ClinVar cross-check. Rewording the tail must not quietly turn
    a warning into a gate, and must not move the fragment an existing test keys on.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\n"
        "module:\n  name: lic\n  title: Lic\n  description: d\n  report_title: Lic\n"
        f"license: {_BINDING}\n",
        encoding="utf-8",
    )
    (spec / "variants.csv").write_text(
        "rsid,gene,genotype,weight,state,conclusion\nrs117385980,SIRT6,C/T,0.1,neutral,c\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs117385980,41249831\n", encoding="utf-8")
    # A complete table, so the module is strict-compilable for reasons unrelated to licensing — the
    # subject here is the warning's text and its non-escalation, and an unresolved coordinate would
    # refuse the compile before either could be observed (RM141).
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs117385980,rs117385980,19,4174111,C,T,GRCh38,0,authored,resolved\n",
        encoding="utf-8",
    )
    (spec / "licensing.csv").write_text(
        "source,layer,license\n"
        f"pmid:41249831,annotation,{_BINDING}\n"
        f"pmid:28399814,annotation,{_PERMISSIVE}\n",
        encoding="utf-8",
    )

    for strict in (False, True):
        compiled = compile_module(spec, tmp_path / f"out{strict}", strict=strict)
        assert compiled.success, compiled.errors
        found = [w for w in compiled.warnings if "declares license" in w]
        assert len(found) == 1, found
        assert "1 of 2 annotation-layer source(s)" in found[0]
