"""`validate` must not report `valid` for a module `compile` then refuses.

AUTHORING.md § 6 puts the two commands one after the other:

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
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec

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


@pytest.mark.parametrize(
    "filename,body,expected",
    [
        (
            "literature.csv",
            "pmid,exists,source,status\n8696333,true,pubmed,checked\n",
            "status",
        ),
        (
            "sources.csv",
            _SOURCES.format(declared_use="non-commercial"),  # the hyphen is wrong; it is `non_commercial`
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
    ],
)
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
