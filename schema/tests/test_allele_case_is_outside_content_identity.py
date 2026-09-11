"""One heterozygote, one content identity, however its author spelled the bases (RM215).

`ALLELE_PATTERN` is `^[ACGT]+$` with `re.IGNORECASE`, so a lowercase allele is legal; the cell is
stored verbatim (`@verbatim-except-order` normalizes the ORDER and nothing else). RM214 fixed the
ordering half — an ASCII sort accepted `A/g` and refused `a/G`, the same unordered pair with two
answers — and left this half open, because it moves an identity key. Measured before the repair:

    'A/G'  sha256:ec8c6bcc…
    'a/G'  sha256:1653d7ee…
    'A/g'  sha256:0b0a1369…
    'a/g'  sha256:78cb573e…

Four content identities for one claim about the genome, which for a *content-dedup* key is the wrong
answer in the same way RM36's build conflation was.

**Why this was legal in a minor, though RM215 was filed for 1.0.** The filing sized it as major "the
same reasoning RM81 applies to a retype", and that citation does not transfer: RM81 is a **parquet
retype** (`List(Utf8)` vs `Utf8`), which P3 names explicitly as major-only. Folding case at hash time
adds nothing, removes nothing and retypes nothing — the authored cell is untouched, `model_dump()` is
unchanged, the parquet column is unchanged, and a reverse-and-recompile round trip is unaffected. What
moves is a *computed* value, which P3 covers under its own heading: a **corrected derivation** "adds,
removes and retypes nothing, so no rule above reaches it", may ship in any release, and may never ship
*silently*. RM36 is the precedent in this very function — `genome_build` was made to feed the hash in
0.5, a minor, on the argument this file re-measures below: only the modules that were being
misidentified move. The declaration lives in `RELEASE_RECORDS["0.7.0"].declared`.

**Scope is measured, not assumed.** The fold reaches the columns whose validator IS that grammar, and
`ref`/`alts` are deliberately not among them: neither is grammar-checked (both accept `zz` today) —
a non-nucleotide there is a *spelling* defect a later pass diagnoses, `@non-nucleotide-spelling` — so
there is no case-insensitivity for them to inherit and folding them would collapse values that really
do differ. `AlleleFunctionRow.allele` is out for the same kind of reason: it is a haplotype *name*
(`*36+*10`), not bases.

**What is left open, deliberately.** `derive_variant_key`'s coordinate fallback does not fold case
either (`1:100:a:g,t` vs `1:100:A:G,T`), which splits *joins and dedup* rather than identity, and
fires only off the VA path — a multi-alt row, or a non-GRCh38 build. That is a wider surface than
RM215 described and it is surfaced rather than fixed here (`@fix-vs-surface`), because it moves a
**stored** cell.
"""

import csv
import importlib
import inspect
import pkgutil
import types
import typing
from pathlib import Path

import just_dna_format
import pytest
from just_dna_format import integrity
from just_dna_format.base import case_insensitive_allele_fields, derive_variant_key
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.release_records import RELEASE_RECORDS
from just_dna_format.spec import VariantRow
from pydantic import BaseModel

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

#: The marked columns, by the CSV that carries them — used only to read the corpus.
_MARKED_COLUMNS = {
    "variants.csv": ("genotype", "effect_allele"),
    "haplotypes.csv": ("allele",),
    "pharm_variants.csv": ("genotype",),
}


def _variant(genotype: str, ref: str = "A", alts: str = "G") -> VariantRow:
    return VariantRow(
        rsid="rs1",
        chrom="1",
        start=100,
        ref=ref,
        alts=alts,
        gene="X",
        genotype=genotype,
        state="risk",
        conclusion="c",
    )


def test_the_four_spellings_of_one_heterozygote_share_one_signature() -> None:
    """The defect, stated as the property that has to hold."""
    signatures = {
        genotype: integrity.content_signature({"variants.csv": [_variant(genotype)]})
        for genotype in ("A/G", "a/G", "A/g", "a/g")
    }

    assert len(set(signatures.values())) == 1, signatures


def test_the_surviving_signature_is_the_upper_case_one() -> None:
    """Which of the four wins is not arbitrary — it is the one every published module already has.

    Folding to lower case would have been just as internally consistent and would have moved the
    signature of every module in existence. This is the whole reason the repair is minor-legal.
    """
    upper = integrity.content_signature({"variants.csv": [_variant("A/G")]})

    for spelling in ("a/G", "A/g", "a/g"):
        assert integrity.content_signature({"variants.csv": [_variant(spelling)]}) == upper


def test_the_authored_cell_is_not_rewritten() -> None:
    """Hash-time only. The CSV on disk still says what its author typed."""
    for spelling in ("a/G", "A/g", "a/g"):
        assert _variant(spelling).genotype == spelling


def test_a_genuinely_different_genotype_still_hashes_differently() -> None:
    """The control. A fold that collapsed real differences would pass every test above."""
    one = integrity.content_signature({"variants.csv": [_variant("A/G")]})
    other = integrity.content_signature({"variants.csv": [_variant("A/A")]})

    assert one != other


def test_ref_and_alts_are_not_folded_because_they_are_not_grammar_checked() -> None:
    """The scope boundary, asserted rather than left in a comment.

    `ref`/`alts` accept a non-nucleotide today and that is deliberate. A field with no grammar has no
    case-insensitivity to inherit, so folding it would collapse two values that genuinely differ.
    """
    assert _variant("A/G", ref="a", alts="g").ref == "a"

    lower = integrity.content_signature({"variants.csv": [_variant("A/G", ref="a", alts="g")]})
    upper = integrity.content_signature({"variants.csv": [_variant("A/G", ref="A", alts="G")]})
    assert lower != upper, (
        "ref/alts were folded. They are not grammar-checked (both accept 'zz'), so a fold there "
        "collapses a spelling defect into the value it is not."
    )


def _string_field(field) -> bool:
    annotation = field.annotation
    if annotation is str:
        return True
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        return set(typing.get_args(annotation)) <= {str, type(None)}
    return False


def _validates(model: type[BaseModel], name: str, value: str) -> bool:
    try:
        for validator in model.__pydantic_decorators__.field_validators.values():
            if name in validator.info.fields:
                func = validator.func
                (func.__func__ if hasattr(func, "__func__") else func)(model, value)
        return True
    except Exception:
        return False


def _all_models() -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for info in pkgutil.iter_modules(just_dna_format.__path__):
        module = importlib.import_module(f"just_dna_format.{info.name}")
        for obj in vars(module).values():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj.__module__ == module.__name__
                and obj not in models
            ):
                models.append(obj)
    return models


def test_the_marked_set_equals_the_set_whose_validator_is_that_grammar() -> None:
    """`@registry-completeness`: an equality over a walked set, re-measured rather than listed.

    A new column validated by `ALLELE_PATTERN` that nobody marks would silently reintroduce the
    defect for its own table, and a marked column whose grammar is *not* case-insensitive would fold
    a value that must stay verbatim. Both directions fail here.

    The probe is behavioural on purpose: an earlier version of it read the validator's source and
    matched `AlleleFunctionRow._validate_allele` on its **name** while its body calls
    `validate_haplotype_name`, which would have folded `*36+*10`.
    """
    marked, measured = set(), set()
    for model in _all_models():
        for name in case_insensitive_allele_fields(model):
            marked.add(f"{model.__name__}.{name}")
        for name, field in model.model_fields.items():
            if not _string_field(field):
                continue
            if not any(
                name in v.info.fields for v in model.__pydantic_decorators__.field_validators.values()
            ):
                continue
            accepts_bases = all(_validates(model, name, v) for v in ("ACGT", "acgt", "g", "G"))
            refuses_other = not any(_validates(model, name, v) for v in ("zz", "ZZ"))
            if accepts_bases and refuses_other:
                measured.add(f"{model.__name__}.{name}")

    assert marked == measured, (
        f"unmarked but case-insensitive: {sorted(measured - marked)}; "
        f"marked but not a nucleotide grammar: {sorted(marked - measured)}"
    )


def test_the_marked_set_is_the_four_columns_this_item_measured() -> None:
    """A floor under the equality above, so a probe that stops matching anything fails loudly."""
    assert case_insensitive_allele_fields(VariantRow) == frozenset({"genotype", "effect_allele"})
    assert case_insensitive_allele_fields(HaplotypeRow) == frozenset({"allele"})
    assert case_insensitive_allele_fields(PharmVariantRow) == frozenset({"genotype"})


def test_no_module_in_the_corpus_carries_a_lowercase_allele() -> None:
    """The measurement the minor-legality argument rests on, re-run rather than quoted.

    If this ever fails, the fold stops being the identity function on the corpus and the claim in
    `RELEASE_RECORDS["0.7.0"]` — that no published signature moves — needs re-measuring with it.
    """
    offenders, inspected = [], 0
    for module in sorted(p for p in _EXAMPLES.iterdir() if p.is_dir()):
        for filename, columns in _MARKED_COLUMNS.items():
            path = module / filename
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as handle:
                for line, row in enumerate(csv.DictReader(handle), start=2):
                    for column in columns:
                        value = row.get(column) or ""
                        if not value:
                            continue
                        inspected += 1
                        if any(char.islower() for char in value):
                            offenders.append(f"{module.name}/{filename}:{line} {column}={value!r}")

    assert inspected > 0, "the scan found no marked cells at all; the column map has drifted"
    assert not offenders, offenders


def test_the_release_record_declares_nothing_because_nothing_published_moved() -> None:
    """Where this correction is recorded, and why it is **not** in `RELEASE_RECORDS`.

    P3 forbids shipping a corrected derivation silently, and the first draft of this item put a
    `DeclaredChange(axis="content_signature", kind="correction")` in the 0.7.0 record. That is a
    contradiction the record already refuses: `test_a_declared_change_names_an_axis_the_record_says
    _moved` requires a declared axis to be one the measurement reports as **moved**, and the
    measurement here is `False` — correctly, because no module in the corpus carries a lowercase
    allele, so no published signature moves.

    The deeper reason is the one that settles it. P3's corrected-derivation clause is written for the
    case where "every artifact compiled earlier holds a value we no longer stand behind"; that is not
    this. Zero artifacts are affected, so there is no movement to declare, and forcing the axis to
    `True` to make room for a declaration would put a false measurement in the record to satisfy a
    rule about honesty. The declaration lives in the CHANGELOG and ROADMAP_HISTORY entries, which are
    what "readable offline and without recompiling" asks for.

    The day a module with a lowercase allele exists, this stops being true — which is what the corpus
    scan above is really guarding.
    """
    assert RELEASE_RECORDS["0.7.0"].axes["content_signature"] is False
    assert not [d for d in RELEASE_RECORDS["0.7.0"].declared if d.item == "RM215"]


@pytest.mark.parametrize("build,ref,alts", [("GRCh38", "a", "g,t"), ("GRCh37", "a", "g")])
def test_the_variant_key_fallback_still_splits_on_case_and_that_is_recorded(
    build: str, ref: str, alts: str
) -> None:
    """Surfaced, not fixed — and pinned so the surfacing cannot rot into a silent fix.

    `derive_variant_key` folds case on the VA path (VRS normalizes) and not on the coordinate
    fallback, which fires for a multi-alt row or a non-GRCh38 build. That splits joins and dedup, and
    repairing it moves a **stored** cell, so it is a different item from this one. If someone fixes
    it, this test fails and sends them to the docstring rather than letting the note go stale.
    """
    lower = derive_variant_key(rsid=None, chrom="1", start=100, ref=ref, alts=alts, build=build)
    upper = derive_variant_key(
        rsid=None, chrom="1", start=100, ref=ref.upper(), alts=alts.upper(), build=build
    )

    assert lower != upper, (
        "the coordinate fallback now folds case. That is a real improvement, but it moves a stored "
        "variant_key — record it as its own item and update RM215's entry."
    )
