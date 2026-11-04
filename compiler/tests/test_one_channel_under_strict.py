"""A finding lives on exactly one channel: the one its severity under the mode picks (RM359).

A mode-ladder finding warns under `best_effort` and refuses under `strict`. Under `strict` it is an
error and **only** an error. Before RM359 `compile --strict` published it twice: `compile_module` ran
its pre-flight (`validate_spec`) in `best_effort` whatever its own mode, seeded `warnings` with every
ladder's best-effort sentence, and then refused with the same finding in `errors`. A consumer counting
findings counted one twice, and the warning half said things the refusal contradicts ("the row is
dropped" beside a compile that dropped nothing and refused).

The resolution ladders had the same defect by a different route: `ResolutionOutcome.warnings` carried
each ladder's warning in both modes, and the compile extended `warnings` with it before refusing with
the paired, longer refusal.

**The rule is asserted over every code that can escalate, not over the one that was reported.** The
roster is the `LadderFinding` walk the feature corpus already asserts its `@ladder` tag against, so a
new ladder member with no fixture here fails `test_every_ladder_code_has_a_case`. Codes are not on the
`CompilationResult` channels (both are plain strings), so each case names a fragment of its
best-effort sentence and the test proves the fragment real on a `best_effort` compile before it
asserts the fragment's absence from a `strict` one, so an absence cannot pass by a typo.
"""

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.base import derive_variant_key

_ROOT = Path(__file__).resolve().parents[2]

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm359\n  title: RM359\n  description: one channel\n  report_title: RM359\n"
    "genome_build: GRCh38\n"
)

#: A real PMID, so mandatory grounding is satisfied by evidence rather than a stub.
_PMID = "16199547"

#: The real GRCh38 HFE C282Y locus (`G>A`, a substitution: a wrong allele has no spelling to hide in).
_HFE_RES = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,authored,resolved\n"
)
_HFE_STUDY = f"rsid,pmid\nrs1800562,{_PMID}\n"

_RES_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,"
    "rsid_alternates,fetched_at\n"
)
_KEY_7_700 = derive_variant_key(None, "7", 700, "C", "G")


def _res(
    key: str, rsid: str, chrom: object, start: object, ref: str, alts: str, idx: int = 0, **kw: str
) -> str:
    status = kw.get("status", "resolved")
    alternates = f'"{kw["alternates"]}"' if kw.get("alternates") else ""
    return f"{key},{rsid},{chrom},{start},{ref},{alts},GRCh38,{idx},manual,{status},{alternates},\n"


@dataclass(frozen=True)
class Case:
    code: str
    #: A fragment of the BEST-EFFORT sentence. Proven present under `best_effort` before its absence
    #: from `strict`'s warnings is asserted.
    fragment: str
    files: dict[str, str] = field(default_factory=dict)


CASES = [
    Case(
        "genotype_allele_not_at_locus",
        "are not among the",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs1800562,6,26092913,G,A,T/T,risk,c\n",
            "studies.csv": _HFE_STUDY,
            "resolution.csv": _HFE_RES,
        },
    ),
    Case(
        "effect_allele_not_at_locus",
        "effect_allele 'T' is not among the",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion,effect_allele\n"
            "rs1800562,6,26092913,G,A,A/A,risk,c,T\n",
            "studies.csv": _HFE_STUDY,
            "resolution.csv": _HFE_RES,
        },
    ),
    Case(
        "study_effect_allele_not_at_locus",
        "inverts the study's finding",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs1800562,6,26092913,G,A,A/A,risk,c\n",
            "studies.csv": f"rsid,pmid,effect_size,effect_measure,effect_allele\nrs1800562,{_PMID},1.7,OR,T\n",
            "resolution.csv": _HFE_RES,
        },
    ),
    Case(
        "p_value_encodings_disagree",
        "two encodings of one number disagree",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs1800562,6,26092913,G,A,A/A,risk,c\n",
            "studies.csv": f"rsid,pmid,p_value,p_value_num\nrs1800562,{_PMID},0.01,0.5\n",
            "resolution.csv": _HFE_RES,
        },
    ),
    Case(
        "symbolic_allele_unusable",
        "row(s) carry",
        {
            # Two rows, so the drop leaves the table non-empty and the finding stays a ladder rather
            # than the both-modes "would annotate nothing at all" refusal.
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs1800562,6,26092913,G,A,A/A,risk,c\n"
            "rs2104016493,2,47410090,T,<DEL>,<DEL>/T,risk,c\n",
            "studies.csv": f"rsid,pmid\nrs1800562,{_PMID}\nrs2104016493,{_PMID}\n",
            "resolution.csv": _HFE_RES,
        },
    ),
    Case(
        "rsid_ambiguous",
        "is a pick, not a finding.",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n,7,700,C,G,C/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs777,29165669\n",
            "resolution.csv": _RES_HEADER
            + _res(_KEY_7_700, "rs777", 7, 700, "C", "G", status="ambiguous", alternates="rs777,rs888"),
        },
    ),
    Case(
        "locus_cannot_host_genotype",
        "rather than emitted as a row asserting an allele it does not have",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\nrs999,,,,,C/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs999,29165669\n",
            "resolution.csv": _RES_HEADER
            + _res("rs999", "rs999", 5, 500, "C", "G", 0)
            + _res("rs999", "rs999", 6, 600, "A", "T", 1),
        },
    ),
    Case(
        "rsid_coordinate_disagrees",
        "(reference disagreement",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\nrs777,7,700,C,G,C/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs777,29165669\n",
            "resolution.csv": _RES_HEADER + _res("rs777", "rs777", 9, 900, "C", "G"),
        },
    ),
]


def _ladder_codes() -> set[str]:
    """The walked roster, loaded from the corpus test that owns it rather than walked a second time."""
    path = _ROOT / "schema" / "tests" / "test_feature_corpus.py"
    spec = importlib.util.spec_from_file_location("_rm359_feature_corpus", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._ladder_codes()


def _spec(root: Path, case: Case) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    for name, text in case.files.items():
        (spec / name).write_text(text)
    return spec


def test_every_ladder_code_has_a_case() -> None:
    """Registry completeness: a new `LadderFinding` code with no fixture here fails, by name.

    `symbolic_allele_unusable` is a case beyond the walk on purpose: its `LadderFinding` wraps a sentence
    a helper built, so the walk (which credits a code literal inside the construction, or in the
    enclosing function) cannot see it, and it escalates all the same.
    """
    missing = _ladder_codes() - {case.code for case in CASES}
    assert not missing, f"ladder code(s) with no one-channel case: {sorted(missing)}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.code)
def test_an_escalated_finding_is_an_error_and_never_also_a_warning(case: Case, tmp_path: Path) -> None:
    spec = _spec(tmp_path, case)

    lenient = compile_module(spec, tmp_path / "best")
    assert lenient.success, lenient.errors
    assert case.code in lenient.manifest.compilation.warnings_summary, (
        f"the fixture does not fire {case.code}: {lenient.manifest.compilation.warnings_summary}"
    )
    assert any(case.fragment in w for w in lenient.warnings), (
        f"fragment {case.fragment!r} is not in any best_effort warning: {lenient.warnings}"
    )

    strict = compile_module(spec, tmp_path / "strict", strict=True)
    assert not strict.success
    assert strict.errors
    both = set(strict.errors) & set(strict.warnings)
    assert not both, f"{case.code}: on both channels in one strict run: {sorted(both)}"
    leaked = [w for w in strict.warnings if case.fragment in w]
    assert not leaked, f"{case.code}: its best_effort sentence is still a warning under strict: {leaked}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.code)
def test_validate_strict_keeps_the_same_rule(case: Case, tmp_path: Path) -> None:
    """`validate --strict` is the pre-flight for `compile --strict`; it owes the same one channel."""
    spec = _spec(tmp_path, case)
    result = validate_spec(spec, strict=True)
    assert not set(result.errors) & set(result.warnings)
    assert not [w for w in result.warnings if case.fragment in w]
