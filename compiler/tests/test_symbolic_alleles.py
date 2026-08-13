"""What a compile does with a symbolic/structural allele it cannot apply (0.6, RM5).

The grammar half is `schema/tests/test_symbolic_alleles.py`. This is the other half: a module is a
declarative rulebook, so a rule nothing can apply is worse than an absent one, and the compiler is
where that judgement lives — the schema deliberately loads a lengthless `<DEL>`, because rejecting it
at load would be fatal in both modes and the decided behaviour is warn-and-drop under `best_effort`.

**Discarding an authored row is new behaviour in this codebase**, so the tests below are built to
watch it happen on real files through the real `compile_module`/`validate_spec` paths rather than to
assert that it would: the parquet is read back and counted, and the round trip is run to a fixed
point. Every variant is a real ClinVar GRCh38 record (large MSH2 and GLI2 deletions, with their
published rsIDs, coordinates and deleted lengths); a fabricated coordinate would make the drop
behaviour look tested while testing nothing about the data it is for.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm5\n"
    "  title: RM5\n"
    "  description: symbolic alleles\n"
    "  report_title: RM5\n"
    "genome_build: GRCh38\n"
)

_RSIDS = ("rs1667266283", "rs2104016493", "rs2469808710")

_VARIANTS_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene,effect_allele\n"

#: Real ClinVar GRCh38 records. `rs1667266283` is a 926 bp MSH2 deletion (chr2:47475521, Pathogenic);
#: `rs2104016493` a 913 bp MSH2 deletion (chr2:47410090); `rs2469808710` a 967 bp GLI2 deletion
#: (chr2:120926480). Read out of the ClinVar VCF, not invented.
_USABLE = (
    "rs1667266283,2,47475521,G,<DEL:926>,<DEL:926>/G,risk,a 926 bp MSH2 deletion,MSH2,<DEL:926>\n"
)
_NO_LENGTH = "rs2104016493,2,47410090,T,<DEL>,<DEL>/T,risk,a deletion with no stated length,MSH2,\n"
_SPELLED = "rs2469808710,2,120926480,A,AT,A/AT,neutral,an ordinary spelled insertion,GLI2,\n"


def _spec(directory: Path, variant_rows: str, **extra: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(_VARIANTS_HEADER + variant_rows)
    # Grounding is mandatory whenever `variants.csv` is present, and `pmid` must denote a real
    # PubMed record. `16199547` is a real PMID already cited by `reference_examples/
    # hfe_hemochromatosis`; it is here to satisfy that requirement, not as a claim that the paper is
    # about these deletions — nothing in this file tests citation content, and inventing a plausible
    # 8-digit number to look authoritative is exactly the failure mode `CitationHint` exists for.
    (directory / "studies.csv").write_text(
        "rsid,pmid\n"
        + "".join(f"{rsid},16199547\n" for rsid in _RSIDS)
    )
    for name, content in extra.items():
        (directory / name.replace("__", ".")).write_text(content)
    return directory


def _weights_rsids(out: Path) -> list[str]:
    return pl.read_parquet(out / "weights.parquet")["rsid"].to_list()


# ── the decided ladder: drop under best_effort, refuse under strict ──────────────────────────────


def test_best_effort_drops_the_lengthless_row_and_keeps_the_rest(tmp_path: Path) -> None:
    """The row is gone from the artifact, not merely flagged — counted off the parquet."""
    spec = _spec(tmp_path / "spec", _USABLE + _NO_LENGTH + _SPELLED)
    result = compile_module(spec, tmp_path / "out")

    assert result.success, result.errors
    assert _weights_rsids(tmp_path / "out") == ["rs1667266283", "rs2469808710"]
    assert "rs2104016493" not in _weights_rsids(tmp_path / "out")


def test_the_warning_says_the_row_was_dropped(tmp_path: Path) -> None:
    """`reverse` cannot re-emit what is not in the parquet, so a warning that merely *flagged* the row
    would leave an author believing their module still carries it."""
    spec = _spec(tmp_path / "spec", _USABLE + _NO_LENGTH)
    result = compile_module(spec, tmp_path / "out")

    dropped = [w for w in result.warnings if "DROPPED" in w]
    assert len(dropped) == 1, result.warnings
    assert "no usable length" in dropped[0]
    assert "row 2" in dropped[0]
    # And it reaches the manifest, which is the only thing a catalog reindexing a published module has.
    assert dropped[0] in result.manifest.compilation.warnings


def test_strict_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """`strict` means a reproducible artifact; an artifact silently smaller than its spec is not one."""
    spec = _spec(tmp_path / "spec", _USABLE + _NO_LENGTH)
    out = tmp_path / "out"
    result = compile_module(spec, out, strict=True)

    assert not result.success
    assert any("no usable length" in e for e in result.errors)
    assert not out.exists(), "a strict refusal must happen before the output directory is made"


def test_a_module_of_nothing_but_unusable_rows_refuses_in_both_modes(tmp_path: Path) -> None:
    """Derived rather than invented: `validate_spec` already refuses a present-but-empty table, so a
    drop that reaches zero would land the module in a state the compiler calls invalid anyway."""
    spec = _spec(tmp_path / "spec", _NO_LENGTH)
    result = compile_module(spec, tmp_path / "out")

    assert not result.success
    assert any("every row was dropped" in e for e in result.errors)


# ── validate must say what compile will do ───────────────────────────────────────────────────────


def test_validate_reports_the_same_finding_at_the_same_severity(tmp_path: Path) -> None:
    """The standing rule: pure computation over authored bytes with no `output_dir` belongs to the
    pre-flight too, or a green `validate` is followed by a refusal the author did not cause. Pinned on
    the *message*, because that identity is also what lets `compile_module` de-duplicate."""
    spec = _spec(tmp_path / "spec", _USABLE + _NO_LENGTH)

    lenient = validate_spec(spec)
    strict = validate_spec(spec, strict=True)
    compiled = compile_module(spec, tmp_path / "out")

    finding = next(w for w in lenient.warnings if "DROPPED" in w)
    assert lenient.valid and finding in compiled.warnings
    assert not strict.valid and finding in strict.errors
    assert not any("DROPPED" in w for w in strict.warnings)


def test_the_finding_is_printed_once_not_twice(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` in `best_effort` whatever its own mode, so a check living
    in both places emits its sentence twice unless the compile side de-duplicates on the message."""
    spec = _spec(tmp_path / "spec", _USABLE + _NO_LENGTH)
    result = compile_module(spec, tmp_path / "out")

    assert len([w for w in result.warnings if "DROPPED" in w]) == 1


# ── the three reason classes, kept apart ─────────────────────────────────────────────────────────


def test_each_reason_gets_its_own_line_with_its_own_consequence(tmp_path: Path) -> None:
    """Grouped by *reason*, never by row — two reasons under one message is the other half of the
    aggregation mistake this codebase has unwound four times in one provider."""
    spec = _spec(
        tmp_path / "spec",
        _USABLE
        + _NO_LENGTH
        + "rs100,2,47410090,<DEL:913>,T,T/T,risk,a symbolic reference allele,MSH2,\n"
        + 'rs101,2,120926480,A,"<*>,<FOO>",A/A,neutral,undeclared names,GLI2,\n',
    )
    result = validate_spec(spec)

    reasons = {
        "no_length": "no usable length",
        "reference_allele": "reference-allele column",
        "unknown_type": "angle-bracketed but not one this format holds",
    }
    for label, fragment in reasons.items():
        matched = [w for w in result.warnings if fragment in w]
        assert len(matched) == 1, (label, result.warnings)
    # Each line names only the alleles its own reason is about.
    unknown = next(w for w in result.warnings if reasons["unknown_type"] in w)
    assert "<*>" in unknown and "<DEL:913>" not in unknown


def test_the_unspecified_allele_is_named_rather_than_generically_refused(tmp_path: Path) -> None:
    """`<*>` is a real token an author consuming a gVCF will paste, and it is an *observability*
    claim rather than a structural one. A diagnosis beats the generic rejection."""
    spec = _spec(tmp_path / "spec", _USABLE + "rs2104016493,2,47410090,T,<*>,T/T,risk,x,MSH2,\n")
    result = validate_spec(spec)

    finding = next(w for w in result.warnings if "<*>" in w)
    assert "observed" in finding


# ── a composite row cannot be dropped, so it refuses instead ─────────────────────────────────────


def test_a_haplotype_definition_refuses_rather_than_losing_a_defining_variant(
    tmp_path: Path,
) -> None:
    """Dropping it would leave the module naming `*5` while describing something else — not a smaller
    module but a quietly different one, which is the one outcome worse than refusing."""
    spec = _spec(
        tmp_path / "spec",
        _USABLE,
        haplotypes__csv=(
            "haplotype_name,rsid,chrom,start,ref,allele,gene\n"
            "*5,rs1667266283,2,47475521,G,<DEL>,MSH2\n"
            "*1,rs2104016493,2,47410090,T,T,MSH2\n"
        ),
    )
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
        assert not result.success, strict
        assert any("fatal in both modes" in e for e in result.errors), strict


# ── determinism and the round trip ───────────────────────────────────────────────────────────────


def test_the_findings_are_byte_stable_across_runs(tmp_path: Path) -> None:
    """They reach `manifest.compilation.warnings`, so their order is artifact-visible: an ordering
    derived from set/dict iteration would move a published manifest between two identical compiles."""
    rows = "".join(
        f"rs{100 + i},2,{47475521 + i},G,<DEL>,<DEL>/G,risk,row {i},MSH2,\n" for i in range(8)
    ) + _USABLE
    spec = _spec(tmp_path / "spec", rows)

    first = validate_spec(spec).warnings
    second = validate_spec(spec).warnings
    assert first == second
    # Aggregated: eight offending rows, one line, and the count is of ROWS rather than of findings —
    # each of these carries the same unusable allele in two columns.
    dropped = [w for w in first if "DROPPED" in w]
    assert len(dropped) == 1 and "8 row(s)" in dropped[0]
    assert "(+" in dropped[0], "a long list must be elided rather than printed in full"


def test_a_kept_symbolic_allele_survives_compile_reverse_compile(tmp_path: Path) -> None:
    """Principle 7 on the new alphabet. The dropped row is deliberately absent from this spec: the
    fixed point is claimed for the module the artifact actually describes, and a discarded row is by
    construction not part of it."""
    spec = _spec(
        tmp_path / "spec",
        _USABLE + "rs2469808710,2,120926480,A,<CNV:TR:967>,<CNV:TR:967>/A,neutral,tr,GLI2,\n",
    )
    first = compile_module(spec, tmp_path / "out1")
    assert first.success, first.errors

    reverse_module(tmp_path / "out1", tmp_path / "spec2")
    second = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert second.success, second.errors

    reverse_module(tmp_path / "out2", tmp_path / "spec3")
    third = compile_module(tmp_path / "spec3", tmp_path / "out3")
    assert third.success, third.errors

    # The alleles came back verbatim, in both the locus and the genotype…
    rebuilt = (tmp_path / "spec2" / "variants.csv").read_text()
    assert "<DEL:926>/G" in rebuilt and "<CNV:TR:967>" in rebuilt
    # …and the cycle is a fixed point on all three identities.
    assert second.manifest.artifact.digest == third.manifest.artifact.digest
    assert second.manifest.content_signature == third.manifest.content_signature
    assert (
        second.manifest.compilation.resolution_signature
        == third.manifest.compilation.resolution_signature
    )


def test_a_symbolic_allele_is_keyed_by_coordinate_not_by_a_minted_identity(
    tmp_path: Path,
) -> None:
    """Forced, not chosen: a VRS allele id is a digest of a *sequence*, and a symbolic allele states
    that the sequence is not known. So it falls through to the coordinate key, exactly as an indel
    already does — no content-addressed identity is minted for something with no content."""
    spec = _spec(tmp_path / "spec", _USABLE)
    result = compile_module(spec, tmp_path / "out")

    keys = pl.read_parquet(tmp_path / "out" / "weights.parquet")["variant_key"].to_list()
    assert result.success and keys == ["rs1667266283"]  # the rsID wins, as always


@pytest.mark.parametrize("spelled", ["<DEL:926>", "<CNV:TR:967>", "<DUP:TANDEM:12>"])
def test_a_symbolic_allele_never_makes_the_module_uncompilable_by_itself(
    tmp_path: Path, spelled: str
) -> None:
    """The widening is the point of the item: each of these must compile under `--strict`, which is
    the mode the authoring workflow tells every author to finish on."""
    spec = _spec(
        tmp_path / f"spec_{spelled.count(':')}_{len(spelled)}",
        f"rs1667266283,2,47475521,G,{spelled},{spelled}/G,risk,c,MSH2,\n",
    )
    result = compile_module(spec, tmp_path / f"out_{len(spelled)}", strict=True)
    assert result.success, result.errors
