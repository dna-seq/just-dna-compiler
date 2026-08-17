"""`validate` must not report `valid` for a module `compile` then refuses.

The documented authoring order puts the two commands one after the other:

    just-dna-compiler validate spec/
    just-dna-compiler compile  spec/ out/ --strict

so `validate` is the author's pre-flight, and its own docstring promises to "validate a module spec
directory without producing output". It did not validate four of the twelve authored tables. Both loops
in `validate_spec` iterate `_TABLE_KINDS`, and `resolution.csv` plus the four 0.5 fact sidecars
(`frequencies.csv`, `gene_metrics.csv`, `literature.csv`, `sources.csv`) are `_FACT_TABLES` — a separate
tuple it never touched. `compile_module` **refuses** on a bad row in any of them.

The sharpest case is `sources.csv`, because the licence gate reads that file and nothing else: a module
drafted entirely from a no-sale source (every PGx upstream) with no `declared_use` recorded validated
clean and then refused to compile, for a reason no authored table showed.

Findings that need *resolved* rows still belong to compile alone, and stay there — this is about the
error channel, which must agree.

**The same gap then reopened one level down: the exemption was applied per *table*, not per *check*.**
Two checks stayed compile-only that read nothing but injected/authored bytes — `_verify_vrs_ids` (a
`resolution.csv` row against its own content-addressed id) and `_check_p_value_num` (two encodings of
one p-value against each other). Neither needs a resolved row; the first is not even mode-dependent,
so `validate` reported `valid` for a module a **plain** `compile` refused as corrupt. `_verify_vrs_ids`
slipped through because "it compares a sidecar" reads like "it is a cross-check", and the cross-checks
genuinely do need resolution — but a self-check on one row consults nothing else.

That also forced the mode question this file now pins: `validate` had no mode at all, so a check whose
severity is the ladder (warning in `best_effort`, error in `strict`) could not be answered for the
compile the author was actually about to run. `validate_spec(strict=…)` mirrors the flag and changes
*severity only* — never which findings exist — which is what keeps one contract instead of two.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.vrs import derive_vrs_allele_id

_YAML = """\
schema_version: "1.0"
module:
  name: agree
  title: Validate/Compile Agreement
  description: fixture
  report_title: Report
genome_build: GRCh38
"""

# CPIC's real terms: CC BY-SA 4.0 plus a contractual no-sale clause, so `commercial_use` is false.
_SOURCES = (
    "source,layer,license,license_url,attribution,share_alike,commercial_use,redistribution,"
    "declared_use,dataset\n"
    "cpic,annotation,CC BY-SA 4.0,https://cpicpgx.org/license/,CPIC,true,false,true,"
    "{declared_use},cpic-2026\n"
)

_DIPLOTYPES = (
    "gene,haplotype_a,haplotype_b,phenotype,conclusion,drug,response,evidence_level\n"
    "CYP2C19,*2,*2,Poor Metabolizer,No CYP2C19 function; avoid clopidogrel,clopidogrel,"
    "reduced active metabolite,1A\n"
)


def _spec(tmp_path: Path, **files: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "diplotypes.csv").write_text(_DIPLOTYPES, encoding="utf-8")
    for name, body in files.items():
        (spec / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return spec


def _both(spec: Path, out: Path) -> tuple[bool, bool]:
    """(validate said valid, compile succeeded) — the pair that must never disagree."""
    return validate_spec(spec).valid, compile_module(spec, out, resolve_with_ensembl=False).success


def test_the_licence_gate_refuses_at_validate_too(tmp_path: Path) -> None:
    """A no-sale annotation source with no declaration: both must refuse, and say the same thing."""
    spec = _spec(tmp_path, sources__csv=_SOURCES.format(declared_use=""))
    result = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)

    assert not result.valid and not compiled.success
    assert any("cpic" in e and "forbid sale" in e for e in result.errors), result.errors
    assert set(result.errors) <= set(compiled.errors)


def test_a_recorded_declaration_passes_both(tmp_path: Path) -> None:
    """The gate is data-driven, so recording the declaration clears it on both sides — this is what
    keeps the test above about the *gate* rather than about `sources.csv` being present at all."""
    spec = _spec(tmp_path, sources__csv=_SOURCES.format(declared_use="non_commercial"))
    assert _both(spec, tmp_path / "out") == (True, True)


# **One case per injected table, and the guard below enumerates the registry rather than this list.**
# RM93: `frequencies.csv` was simply absent here, so `_check_frequency_arithmetic` had no path through
# `validate_spec` in any test and the file's own promise went unkept for a whole release. A list of
# tables somebody remembered is exactly the failure this file was written about, one level up —
# `@parity-by-check` says audit by check, and the least a fixture list can do is not be shorter than
# the registry. Four of the seven fact tables were missing when that was first counted.
_INJECTED_ROW_CASES: tuple[tuple[str, str, str], ...] = (
        (
            "literature.csv",
            "pmid,exists,source,status\n8696333,true,pubmed,checked\n",
            "status",
        ),
        (
            "frequencies.csv",
            (
                "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,"
                "allele_number,dataset,source,status\n"
                "rs1800562,rs1800562,6,26092913,G,A,GRCh38,global,3,1613660,gnomad_v4.1_joint,"
                "gnomad,checked\n"
            ),
            "status",
        ),
        (
            "gene_validity.csv",
            (
                "gene,disease_id,disease_label,moi,classification,dataset,source,status\n"
                "HFE,MONDO:0011072,hereditary haemochromatosis,autosomal_recessive,definitive,"
                "clingen_gene_validity_2026-06,clingen,checked\n"
            ),
            "status",
        ),
        (
            "clinical_assertions.csv",
            (
                "variant_key,rsid,chrom,start,ref,alt,genome_build,clin_sig,dataset,source,status\n"
                "rs1800562,rs1800562,6,26092913,G,A,GRCh38,pathogenic,clinvar_2026-06-27,"
                "clinvar,checked\n"
            ),
            "status",
        ),
        (
            "gwas_effects.csv",
            (
                "association_id,variant_key,rsid,effect_allele,effect_size,dataset,source,status\n"
                "GCST000001,rs1800562,rs1800562,A,0.12,gwas_catalog_2026-06,gwas_catalog,checked\n"
            ),
            "status",
        ),
        (
            "sources.csv",
            # This case used to be spelled `non-commercial`, on the reasoning that the hyphen is wrong
            # where the member is `non_commercial`. It no longer is: a `-`/`_` slip in a hand-written
            # cell is now canonicalized to the declared member, which is the whole point — the fact
            # that a test author reached for the hyphen as the obvious *plausible* mistake is the
            # evidence that it was worth absorbing. What is left here is a value that names nothing.
            _SOURCES.format(declared_use="commerical"),
            "declared_use",
        ),
        (
            "resolution.csv",
            (
                "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
                "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,cache,checked\n"
            ),
            "status",
        ),
        (
            "gene_metrics.csv",
            (
                "gene,dataset,source,status,haploinsufficiency\n"
                "HFE,gnomad_v4.1_constraint,gnomad,resolved,very likely\n"
            ),
            "haploinsufficiency",
        ),
)


def test_every_injected_table_has_a_parity_case() -> None:
    """The guard that enumerates instead of remembering (RM93).

    `test_an_invalid_injected_row_fails_validate_not_only_compile` walks a literal list, and a literal
    list is only as complete as the person who wrote it: `frequencies.csv` was never in it, so the
    table whose arithmetic check `validate_spec` did not call was also the table this file did not
    exercise. Two independent misses with one cause, which is what makes the registry — not the list —
    the right thing to iterate.

    Derived from `_FACT_TABLES` for the same reason `_INPUT_FILES` is (`@fieldnames-from-model`): a
    hand-kept parallel list goes stale the moment the eighth sidecar lands.
    """
    from just_dna_compiler.compiler import _FACT_TABLES

    registry = {"resolution.csv", *(name for name, _parquet, _model in _FACT_TABLES)}
    covered = {filename for filename, _body, _expected in _INJECTED_ROW_CASES}
    assert registry <= covered, (
        f"no validate/compile parity case for {sorted(registry - covered)} — add one to "
        f"_INJECTED_ROW_CASES rather than deleting this assertion"
    )


@pytest.mark.parametrize("filename,body,expected", _INJECTED_ROW_CASES)
def test_an_invalid_injected_row_fails_validate_not_only_compile(
    tmp_path: Path, filename: str, body: str, expected: str
) -> None:
    """One bad cell in each injected table. Every one of these used to pass `validate` and refuse at
    `compile`, naming a column the author had just been told was fine."""
    spec = _spec(tmp_path, **{filename.replace(".", "__"): body})
    result = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)

    assert not result.valid, f"{filename} validated clean"
    assert not compiled.success
    assert any(filename in e and expected in e for e in result.errors), result.errors


def test_a_valid_sidecar_set_still_validates(tmp_path: Path) -> None:
    """The negative control: the new checks must not refuse a correct module. Every reference example
    covers this too, but keeping it beside the failures makes the pair legible."""
    spec = _spec(
        tmp_path,
        sources__csv=_SOURCES.format(declared_use="non_commercial"),
        literature__csv="pmid,exists,source,status\n8696333,true,pubmed,resolved\n",
    )
    result = validate_spec(spec)
    assert result.valid, result.errors


def test_validate_reads_sources_csv_as_the_gate_does(tmp_path: Path) -> None:
    """Not a second parser: the gate must key on the same column the compiler's does, so flipping only
    `commercial_use` is what changes the verdict."""
    permissive = _SOURCES.format(declared_use="").replace(",true,false,true,", ",true,true,true,")
    spec = _spec(tmp_path, sources__csv=permissive)
    assert _both(spec, tmp_path / "out") == (True, True)


def test_a_yaml_syntax_error_is_reported_not_raised(tmp_path: Path) -> None:
    """An unclosed bracket is the likeliest mistake in a hand-written file, and `_load_yaml` parsed
    outside its own try/except — so `validate` died with a `yaml.parser.ParserError` traceback instead
    of locating the problem. pyyaml's message already names line and column, so it is kept."""
    spec = _spec(tmp_path)
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: agree\n  title: [unclosed\n", encoding="utf-8"
    )
    result = validate_spec(spec)
    assert not result.valid
    assert any("not valid YAML" in e and "line 4" in e for e in result.errors), result.errors


def test_a_yaml_scalar_is_reported_as_the_wrong_shape(tmp_path: Path) -> None:
    """Valid YAML, wrong shape. It used to reach `model_validate` and come back as a pydantic message
    about input types rather than about the file."""
    spec = _spec(tmp_path)
    (spec / "module_spec.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    result = validate_spec(spec)
    assert not result.valid
    assert any("must be a mapping" in e for e in result.errors), result.errors


# ── The per-check half: injected/authored bytes only, so both commands must see them ───────────────

# Real rows. rs334 (sickle-cell, HbS) at GRCh38 11:5227002 T>A, and MTHFR 677 at 1:11796321 G>A — the
# id is computed here rather than pasted so the fixture cannot drift from the minting code.
_HBS = derive_vrs_allele_id("11", 5227002, "T", "A")
_MTHFR_677 = derive_vrs_allele_id("1", 11796321, "G", "A")

_RESOLUTION_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,source,status\n"
)


def _resolution(vrs_id: str) -> str:
    """rs334's real locus, carrying whichever `vrs_id` the caller wants tested against it."""
    return _RESOLUTION_HEADER + (
        f"{_HBS},rs334,11,5227002,T,A,GRCh38,0,{vrs_id},2.0,gnomad,resolved\n"
    )


def _studies(p_value: str, p_value_num: str) -> str:
    """One real citation (PMID 16199547, an HbS association) carrying the two p-value encodings."""
    return "rsid,pmid,p_value,p_value_num\n" f"rs334,16199547,{p_value},{p_value_num}\n"


def _agree(spec: Path, out: Path, *, strict: bool) -> tuple[bool, bool]:
    """(validate said valid, compile succeeded) at one mode — the pair that must never disagree."""
    return (
        validate_spec(spec, strict=strict).valid,
        compile_module(spec, out, resolve_with_ensembl=False, strict=strict).success,
    )


def test_a_correct_vrs_id_is_clean_on_both_sides(tmp_path: Path) -> None:
    """The negative control, and it matters here: the check must not refuse a correctly minted id, or
    the two tests below would pass for the wrong reason."""
    spec = _spec(tmp_path, resolution__csv=_resolution(_HBS))
    assert _agree(spec, tmp_path / "out", strict=False) == (True, True)
    assert _agree(spec, tmp_path / "out_s", strict=True) == (True, True)


@pytest.mark.parametrize("strict", [False, True])
def test_a_corrupt_vrs_id_refuses_at_validate_too_in_both_modes(
    tmp_path: Path, strict: bool
) -> None:
    """A substitution's VA is deterministic with no reference, so a mismatch can only be corruption —
    an error in *both* modes. This is the case that made the gap reachable without `--strict` at all:
    `validate` blessed a module a plain `compile` then rejected.

    The id carried is a *real other allele's* (MTHFR 677) rather than a mangled string, so the row is
    well-formed and only the identity is wrong — the shape a hand-built or externally produced
    `resolution.csv` actually fails in.
    """
    spec = _spec(tmp_path, resolution__csv=_resolution(_MTHFR_677))
    result = validate_spec(spec, strict=strict)
    compiled = compile_module(
        spec, tmp_path / f"out_{strict}", resolve_with_ensembl=False, strict=strict
    )

    assert not result.valid and not compiled.success
    assert any("does not match the id recomputed" in e for e in result.errors), result.errors
    assert set(result.errors) <= set(compiled.errors)


def test_a_p_value_transcription_slip_follows_the_mode_ladder_on_both_sides(
    tmp_path: Path,
) -> None:
    """`p_value="1.2e-14"` beside `p_value_num=1.2e-41` — the exponent digits transposed on the way
    into the queryable column. The string is the record; the number is what a consumer filters on, so
    they disagree by ten orders of magnitude with nothing malformed about either cell.

    Severity is the ladder, and `validate` must report the same rung as the compile the author is
    about to run: a warning that still validates in `best_effort`, a refusal in `strict`.
    """
    spec = _spec(tmp_path, studies__csv=_studies("1.2e-14", "1.2e-41"))

    assert _agree(spec, tmp_path / "be", strict=False) == (True, True)
    assert _agree(spec, tmp_path / "st", strict=True) == (False, False)

    lenient = validate_spec(spec, strict=False)
    assert any("p_value_num says" in w for w in lenient.warnings), lenient.warnings
    strict_result = validate_spec(spec, strict=True)
    assert any("p_value_num says" in e for e in strict_result.errors), strict_result.errors


def test_the_p_value_finding_is_published_once(tmp_path: Path) -> None:
    """One authored disagreement, one sentence in the manifest (RM94).

    `_check_p_value_num` runs in `validate_spec` and again in `compile_module` -- correctly, because
    the inner pass is always best_effort and the re-run in the caller's mode is what lets `--strict`
    escalate. What was wrong is that the compile-side `extend` carried no `if w not in all_warnings`
    filter, which every neighbouring re-run does, so a best_effort compile published the identical
    sentence twice into `manifest.compilation.warnings`.

    Asserts the **count of the finding**, not the length of the list: other warnings (the closure
    notice, for one) legitimately share the field, and a length assertion would break on any of them.
    """
    spec = _spec(tmp_path, studies__csv=_studies("1.2e-14", "1.2e-41"))
    compiled = compile_module(spec, tmp_path / "once", resolve_with_ensembl=False)

    assert compiled.success
    findings = [w for w in compiled.manifest.compilation.warnings if "p_value_num says" in w]
    assert len(findings) == 1, findings


def test_an_agreeing_p_value_pair_is_silent(tmp_path: Path) -> None:
    """A rounding is not a contradiction: the comparison is relative at 1%, so the transcription that
    dropped a digit still agrees with its string."""
    spec = _spec(tmp_path, studies__csv=_studies("5.23e-8", "5.2e-8"))
    assert _agree(spec, tmp_path / "out", strict=True) == (True, True)
    assert not any("p_value_num" in m for m in validate_spec(spec, strict=True).warnings)


@pytest.mark.parametrize("strict", [False, True])
def test_an_unverifiable_indel_reads_the_same_in_both_modes_and_both_commands(
    tmp_path: Path, strict: bool
) -> None:
    """`strict` is a severity dial over findings the mode is *about* — and this one it is not about.

    An indel's id cannot be recomputed in this tier: justifying one needs the reference sequence, which
    the compiler has no access to and will never fetch. That is a limit of the tier, unfixable by any
    edit to the module, so it warns on every rung — and it must read identically from `validate` and
    from `compile`, which is what this file exists to guarantee. It used to escalate under `--strict`,
    and the consequence was that the enricher's own online indel minting produced modules the compiler
    refused; the mode-ladder findings this file pins elsewhere (`p_value_num`, allele membership) are
    the ones where an author really can act on the report.

    The wording is pinned too, because "could not be verified" and "does not match" are different
    claims and only one of them was reached.
    """
    indel = "ga4gh:VA.LNB3XTeT4xdXxnKyg_RjJhLp5RnUlMpL"  # a real VA, for a 1 bp insertion
    spec = _spec(
        tmp_path,
        resolution__csv=_RESOLUTION_HEADER
        + f"{_HBS},rs334,11,5227002,C,CA,GRCh38,0,{indel},2.0,clinvar,resolved\n",
    )
    assert _agree(spec, tmp_path / f"out_{strict}", strict=strict) == (True, True)

    result = validate_spec(spec, strict=strict)
    assert any("could not be verified" in w for w in result.warnings), result.warnings
    assert not any("does not match" in m for m in result.errors + result.warnings)


# ── allele membership: the third check that was compile-only, found the same way ─────────────────

_MEMBERSHIP_VARIANTS = (
    "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "19,44908684,T,{alts},C/T,risk,fixture,APOE\n"
)
_MEMBERSHIP_STUDIES = "chrom,start,ref,pmid,conclusion\n19,44908684,T,16199547,fixture\n"


@pytest.mark.parametrize("strict", [False, True])
def test_allele_membership_answers_at_validate_too(tmp_path: Path, strict: bool) -> None:
    """`_check_allele_membership` was compile-only, and it is a mode ladder — so `validate --strict`
    reported `valid` for a module `compile --strict` refused.

    The same defect this file exists for, one check further along: the 2026-08-07 pass went table by
    table, and this one reads *authored* rows rather than a sidecar, so "which tables does validate
    read" could not surface it. Its own docstring already says it runs on the authored rows **before**
    resolution expands them, which is precisely why it is computable with no resolution step.

    Uses a non-nucleotide locus allele because that shape needs no `resolution.csv` at all — the row
    authors its own `ref`/`alts`, so the membership set is decided from authored bytes alone, which is
    the property that makes the check belong at pre-flight.
    """
    spec = _spec(
        tmp_path / f"m{int(strict)}",
        variants__csv=_MEMBERSHIP_VARIANTS.format(alts="Y"),
        studies__csv=_MEMBERSHIP_STUDIES,
    )
    validated, compiled = _agree(spec, tmp_path / f"o{int(strict)}", strict=strict)

    assert validated == compiled, "validate and compile disagreed about the same module"
    assert validated is not strict, "a mode ladder: clean in best_effort, refused under strict"


def test_a_nucleotide_locus_is_clean_on_both_sides(tmp_path: Path) -> None:
    """Negative control: the check must not fire on an ordinary locus, or the test above passes for
    the wrong reason — and `alts=C` is the very allele the ambiguity code `Y` stands for."""
    spec = _spec(
        tmp_path / "ok",
        variants__csv=_MEMBERSHIP_VARIANTS.format(alts="C"),
        studies__csv=_MEMBERSHIP_STUDIES,
    )
    assert _agree(spec, tmp_path / "ok_out", strict=False) == (True, True)
    assert _agree(spec, tmp_path / "ok_out_s", strict=True) == (True, True)


def test_the_membership_message_is_identical_on_both_sides(tmp_path: Path) -> None:
    """Same finding, same words. Two phrasings of one defect is how the two commands drift into
    being two contracts, which is what the module docstring above is about."""
    spec = _spec(
        tmp_path / "msg",
        variants__csv=_MEMBERSHIP_VARIANTS.format(alts="Y"),
        studies__csv=_MEMBERSHIP_STUDIES,
    )
    from_validate = [w for w in validate_spec(spec).warnings if "not among the" in w]
    from_compile = [
        w
        for w in compile_module(
            spec, tmp_path / "msg_out", resolve_with_ensembl=False
        ).warnings
        if "not among the" in w
    ]
    assert from_validate == from_compile != []
    assert "IUPAC ambiguity code" in from_validate[0]


# ── RM93: the two checks that were still compile-only, and the composition that hid one ────────────


def _frequencies(allele_count: int, allele_number: int) -> str:
    """One gnomAD-shaped row whose two counts the caller decides. Real locus (HFE C282Y)."""
    return (
        "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,allele_number,"
        "dataset,source,status\n"
        f"rs1800562,rs1800562,6,26092913,G,A,GRCh38,global,{allele_count},{allele_number},"
        f"gnomad_v4.1_joint,gnomad,resolved\n"
    )


@pytest.mark.parametrize("strict", [False, True])
def test_frequency_arithmetic_refuses_at_validate_too(tmp_path: Path, strict: bool) -> None:
    """`_check_frequency_arithmetic` was never called from `validate_spec` at all (RM93).

    Not a row-level failure — every cell here is a well-formed integer and the row loads on both
    sides. What is impossible is the *relation* between two of them, which is why the table-level
    check is the only thing that can see it, and why the parametrized row-level cases above could
    never have caught this however many tables they covered.

    Its integer half returns **errors**, not warnings, so this is the plain-mode variety of the gap:
    `validate` reported `valid` for a module a plain `compile` refused. Parametrized over both modes
    to pin that the severity does not depend on the ladder.
    """
    spec = _spec(tmp_path / f"f{int(strict)}", frequencies__csv=_frequencies(500, 100))
    result = validate_spec(spec, strict=strict)
    compiled = compile_module(
        spec, tmp_path / f"fo{int(strict)}", resolve_with_ensembl=False, strict=strict
    )

    assert not result.valid and not compiled.success
    assert any("cannot be larger than its own denominator" in e for e in result.errors), result.errors
    assert set(result.errors) <= set(compiled.errors)


def test_possible_frequency_arithmetic_is_clean_on_both_sides(tmp_path: Path) -> None:
    """Negative control: the check must not refuse counts that can coexist, or the test above passes
    for the wrong reason — 3 of 1613660 is HFE C282Y's real global frequency."""
    spec = _spec(tmp_path / "fok", frequencies__csv=_frequencies(3, 1613660))
    assert _agree(spec, tmp_path / "fok_out", strict=True) == (True, True)


# Keyed under the **rsID**, because that is the key a study row derives: `StudyRow` here carries no
# coordinate, so `derive_variant_key` returns `rs334` and the membership lookup has to find it there.
# An rsid-authored module is exactly the shape whose `resolution.csv` is written under the rsID.
_TABLE_ONLY_RESOLUTION = (
    _RESOLUTION_HEADER + f"rs334,rs334,11,5227002,T,A,GRCh38,0,{_HBS},2.0,gnomad,resolved\n"
)


@pytest.mark.parametrize("strict", [False, True])
def test_a_module_with_no_variants_csv_still_gets_the_study_allele_check(
    tmp_path: Path, strict: bool
) -> None:
    """The composition every fixture in this file was missing (RM93).

    `_check_study_effect_alleles` sat inside `validate_spec`'s `if variants:` block while running
    unconditionally on the compile side, so it never ran for the one shape it was written for: a
    module with a table kind, `studies.csv` and `resolution.csv` and **no** `variants.csv`. Every
    study fixture above writes `_MEMBERSHIP_VARIANTS` beside `_MEMBERSHIP_STUDIES`, so `if variants:`
    was always true and this shape was never constructed — the gate was invisible to a suite that
    only ever asked well-composed questions.

    `_spec` always writes `diplotypes.csv`, so the module is a legal table-only one; the effect allele
    named is C at a T/A locus, which the injected table can settle without any authored variant row.
    """
    spec = _spec(
        tmp_path / f"t{int(strict)}",
        resolution__csv=_TABLE_ONLY_RESOLUTION,
        studies__csv="rsid,pmid,effect_allele,effect_size\nrs334,16199547,C,0.5\n",
    )
    assert not (spec / "variants.csv").exists(), "the fixture must stay table-only"

    validated, compiled = _agree(spec, tmp_path / f"to{int(strict)}", strict=strict)
    assert validated == compiled, "validate and compile disagreed about a table-only module"
    assert validated is not strict, "a mode ladder: clean in best_effort, refused under strict"

    reported = validate_spec(spec, strict=strict)
    findings = reported.errors if strict else reported.warnings
    assert any("not among the resolved alleles" in m for m in findings), findings


def test_a_table_only_module_with_a_hosted_effect_allele_is_clean(tmp_path: Path) -> None:
    """Negative control for the composition: A *is* an allele the locus hosts."""
    spec = _spec(
        tmp_path / "tok",
        resolution__csv=_TABLE_ONLY_RESOLUTION,
        studies__csv="rsid,pmid,effect_allele,effect_size\nrs334,16199547,A,0.5\n",
    )
    assert _agree(spec, tmp_path / "tok_out", strict=True) == (True, True)
