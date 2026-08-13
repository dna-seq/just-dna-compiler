"""An unbuilt assembly is a check this tier CANNOT put, and the attestation has to say so (D2, RM45).

`verify_reference_alleles` reached `refget_accession(row.chrom, row.genome_build)`, caught
`UnsupportedBuildError` and `continue`d — a per-row skip indistinguishable from "this row had no
coordinate". So on a `genome_build: GRCh37` module every row fell out of `subjects`, `not_checked`
stayed `None`, and the pass reported as having **run**, over zero rows. `verification.json` then
published

    reference_allele        subjects 0  findings 0  skipped null
    genome_build_agreement  subjects 0  findings 0  skipped nothing_to_check
                            "no authored ref disagreed with the reference, …"

for a module on which nothing was compared, and the second line asserts a comparison that never
happened. `_verification_records` guards exactly this contradiction for two of the three ways the
subject list can empty (the ref check did not run; it ran offline); the third — it ran and had no
subjects, because the assembly has no refget table — was the one that was missed.

`VALID_VERIFICATION_SKIPS` already carried the member, with this case named in its own comment
(`"unsupported"`, "this tier cannot put the question for these rows (e.g. an unbuilt assembly)"), and
nothing in the workspace emitted it or asserted it.

Reproduced on `reference_examples/grch37_build` rather than on an invented fixture: it is the corpus
module whose whole purpose is a build this tier does not resolve, it carries real `ref` values, and
it had been publishing the false attestation.
"""

from pathlib import Path

from just_dna_enricher.sequences import SequenceProxy, verify_reference_alleles
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import refget_supports_build

_GRCH37 = [
    # `reference_examples/grch37_build`'s own two HFE rows, verbatim.
    ResolutionRow(variant_key="6:26093141:G:A", chrom="6", start=26093141, ref="G", alts="A",
                  genome_build="GRCh37", source="authored", status="resolved"),
    ResolutionRow(variant_key="6:26091179:C:G", chrom="6", start=26091179, ref="C", alts="G",
                  genome_build="GRCh37", source="authored", status="resolved"),
]


def test_the_build_predicate_separates_the_two_negatives() -> None:
    """`refget_supports_build` answers the assembly question `refget_accession` raises on."""
    assert refget_supports_build("GRCh38") is True
    assert refget_supports_build("GRCh37") is False
    # An unset build is the format's default, not an unbuilt assembly.
    assert refget_supports_build(None) is True and refget_supports_build("") is True


def test_a_grch37_module_is_unsupported_not_a_clean_pass() -> None:
    """The whole finding in one assertion: `not_checked` is set, so nothing downstream reads a pass.

    `subjects == 0` alone was never enough — the old value was `(mismatches=[], subjects=0,
    not_checked=None)`, which is byte-identical to a GRCh38 module whose every row was a symbolic
    allele, and the attestation renders the two differently only because of `not_checked`.
    """
    check = verify_reference_alleles(_GRCH37, sequences=SequenceProxy(offline=True))
    assert check.not_checked == "unsupported"
    assert check.subjects == 0 and check.mismatches == []


def test_offline_still_outranks_it_for_a_supported_build() -> None:
    """The reasons stay distinct and keep their old meanings for a GRCh38 module."""
    rows = [
        ResolutionRow(variant_key="6:26092913:G:A", chrom="6", start=26092913, ref="G", alts="A",
                      genome_build="GRCh38", source="authored", status="resolved")
    ]
    assert verify_reference_alleles(rows, sequences=SequenceProxy(offline=True)).not_checked == (
        "offline"
    )


def test_a_mixed_module_is_not_written_off() -> None:
    """One unbuilt-assembly row does not make the whole pass unsupported.

    The skip is a statement about the *module*, so it is decided from the build set and only when
    **no** row is on a supported assembly. A single stray GRCh37 row beside GRCh38 ones must leave
    the pass to run over the rows it can read — which is what `refget_accession`'s per-row
    `UnsupportedBuildError` catch is still there for.
    """
    mixed = [
        *_GRCH37,
        ResolutionRow(variant_key="6:26092913:G:A", chrom="6", start=26092913, ref="G", alts="A",
                      genome_build="GRCh38", source="authored", status="resolved"),
    ]
    # Offline, so the reason is the sequence proxy's, not the build's — the point is that it is
    # *not* `unsupported`.
    assert verify_reference_alleles(mixed, sequences=SequenceProxy(offline=True)).not_checked != (
        "unsupported"
    )


def test_the_corpus_module_attests_unsupported_end_to_end(tmp_path: Path) -> None:
    """`enrich` on the real GRCh37 example, offline: both records name the reason.

    `genome_build_agreement` is the half that was actively false — it took its clean branch and said
    "no authored ref disagreed with the reference" about a module where no ref was read — so the
    assertion is that it now carries the ref check's own reason rather than a verdict.
    """
    from just_dna_enricher.enrich import enrich

    spec = tmp_path / "grch37_build"
    source = Path(__file__).resolve().parents[2] / "reference_examples" / "grch37_build"
    spec.mkdir()
    for name in ("module_spec.yaml", "variants.csv", "studies.csv"):
        (spec / name).write_text((source / name).read_text())

    enrich(spec, offline=True)

    import json

    records = {r["check"]: r for r in json.loads((spec / "verification.json").read_text())["records"]}
    assert records["reference_allele"]["skipped"] == "unsupported"
    assert records["genome_build_agreement"]["skipped"] == "unsupported"
    # And the detail no longer blames the network for an assembly problem.
    assert "refget" in records["reference_allele"]["detail"]
