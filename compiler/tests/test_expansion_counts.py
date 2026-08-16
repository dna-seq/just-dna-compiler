"""`expanded_keys` / `expanded_rows`: an artifact says whether it contains expansion rows (S33).

A one-to-many rsID is paired with every locus it resolves to, so an authored genotype becomes N rows
of which **one** can match. The other N-1 are well-formed: correct grammar, the module's own
conclusion, a locus whose alleles cannot carry that genotype. A reporting consumer read 2,579 of them
as reference genotypes their subject carried, caught before rendering — and could not have known from
the artifact that any such row was there, because nothing in `weights.parquet` distinguishes an
expanded row from an authored one.

The expansion itself is not the defect and is not changed here (COMPILER.md § Resolution says why, and
Principle 7 forbids the obvious prune). What these two counts add is the artifact-level answer to
*does this module contain them at all*.

Every expectation is derived at runtime — from the module's own `resolution.csv`, from another
manifest field, or from a fixture this file writes and can therefore count. Nothing is a number read
off a data dump.
"""

import csv
import io
import json
from collections import Counter
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _example_dirs() -> list[Path]:
    return sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())


def _multi_locus_keys(spec_dir: Path) -> set[str]:
    """Keys the injected table resolves onto more than one locus — the expansion's *candidates*.

    A ceiling, not a prediction: `_hostable_loci` may reject a locus whose alleles contradict the
    authored genotype, and a coordinate-authored row never enters the expansion path at all. So the
    tests below bracket rather than equate, which is the same choice `test_resolution_subjects.py`
    makes and for the same reason — predicting the number means re-implementing the transform.
    """
    path = spec_dir / "resolution.csv"
    if not path.is_file():
        return set()
    counts = Counter(row["variant_key"] for row in csv.DictReader(io.StringIO(path.read_text())))
    return {key for key, n in counts.items() if n > 1}


@pytest.mark.parametrize("spec_dir", _example_dirs(), ids=lambda d: d.name)
def test_the_two_counts_agree_with_each_other_and_with_the_subject_count(
    spec_dir: Path, tmp_path: Path
) -> None:
    """Four invariants that hold on every module the counts were established for.

    The third is the one worth having: an expanded key contributes at least two rows by definition, so
    a pair like `keys=3, rows=3` would mean the counts were measuring different things. The fourth
    ties them to the denominator they are a part of.
    """
    result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None
    compilation = result.manifest.compilation

    keys, rows = compilation.expanded_keys, compilation.expanded_rows
    # Jointly established or jointly not — half a measurement is the state this pair may never be in.
    assert (keys is None) == (rows is None)
    if keys is None or rows is None:
        return

    assert (keys == 0) == (rows == 0)
    assert rows >= 2 * keys
    assert rows <= compilation.resolution_subjects
    assert keys <= len(_multi_locus_keys(spec_dir))


def test_the_counts_are_established_exactly_where_resolution_had_something_to_do(
    tmp_path: Path,
) -> None:
    """`None` is a claim about the *run*, not about the module, so pin which runs make one.

    The path fires when there is a `variants.csv` to resolve and a `resolution.csv` to resolve it
    from, on the build the compiler resolves (GRCh38 — RM15). Miss any of the three and nothing
    looked, which is why the corpus's table-only and GRCh37 modules must read `None` rather than
    zero: a catalog cannot tell "no expansion" from "no measurement" if they share a value.
    """
    established: set[str] = set()
    resolvable: set[str] = set()
    for spec_dir in _example_dirs():
        result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
        assert result.success, result.errors
        assert result.manifest is not None
        if result.manifest.compilation.expanded_keys is not None:
            established.add(spec_dir.name)
        if (
            (spec_dir / "variants.csv").is_file()
            and (spec_dir / "resolution.csv").is_file()
            and result.manifest.genome_build == "GRCh38"
        ):
            resolvable.add(spec_dir.name)

    assert established == resolvable
    # Both halves must be non-empty or the equality is satisfiable by an empty corpus.
    assert resolvable and {d.name for d in _example_dirs()} - resolvable


def test_the_corpus_modules_that_expand_are_exactly_the_ones_with_multi_locus_keys(
    tmp_path: Path,
) -> None:
    """Set equality over the corpus, so a module silently losing its expansion is a failure.

    Both sides are measured: the left off `manifest.json`, the right off each module's own
    `resolution.csv`. The examples happen to make the ceiling tight — every multi-locus key in this
    corpus is rsID-authored and hostable at both loci — which is *not* a general guarantee, so the
    per-module test above keeps the inequality and this one asserts membership rather than counts.
    """
    expanding: set[str] = set()
    candidates: set[str] = set()
    for spec_dir in _example_dirs():
        result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
        assert result.success, result.errors
        assert result.manifest is not None
        if result.manifest.compilation.expanded_keys:
            expanding.add(spec_dir.name)
        if _multi_locus_keys(spec_dir):
            candidates.add(spec_dir.name)

    assert expanding == candidates
    assert candidates, "the corpus must keep a one-to-many module or this proves nothing"


def _two_genotype_expansion(spec_dir: Path) -> Path:
    """The reported shape: one rsID, two authored genotypes, two resolved loci.

    Built from `pathogenic_clinvar`'s own rows rather than invented — `rs1554917888` is ClinVar
    Variation 428095 (`T>TA`, a duplication) and 2583495 (`TA>T`, the reciprocal deletion) under one
    rsID, both pathogenic, which is the pair the report was about. The second authored genotype
    `TA/TA` is what the reporting consumer's panel wrote for the duplication homozygote, and it is the
    row that lands beside `ref=TA` as a reference homozygote.
    """
    source = _EXAMPLES / "pathogenic_clinvar"
    rsid = "rs1554917888"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "module_spec.yaml").write_text(
        (source / "module_spec.yaml").read_text().replace("pathogenic_hbb", "expansion_probe")
    )
    variants = (source / "variants.csv").read_text().splitlines()
    authored = [variants[0]] + [line for line in variants if line.startswith(f"{rsid},")]
    assert len(authored) == 2, "the fixture assumes the example authors this rsID exactly once"
    # The example's own row is `T/TA`; add the homozygote beside it, changing nothing else.
    authored.append(authored[1].replace(",T/TA,", ",TA/TA,"))
    (spec_dir / "variants.csv").write_text("\n".join(authored) + "\n")

    resolution = (source / "resolution.csv").read_text().splitlines()
    loci = [line for line in resolution if line.startswith(f"{rsid},")]
    assert len(loci) == 2, "the fixture assumes this rsID resolves onto exactly two loci"
    (spec_dir / "resolution.csv").write_text("\n".join([resolution[0], *loci]) + "\n")

    (spec_dir / "studies.csv").write_text(f"rsid,chrom,start,ref,pmid\n{rsid},,,,29165669\n")
    literature = (source / "literature.csv").read_text().splitlines()
    (spec_dir / "literature.csv").write_text(
        "\n".join([literature[0], *(x for x in literature if x.startswith("29165669,"))]) + "\n"
    )
    return spec_dir


def test_the_row_count_is_the_product_not_the_locus_count(tmp_path: Path) -> None:
    """Two authored genotypes over two loci is **four** rows, and the count says four.

    This is the half a per-locus number gets wrong. `expanded_keys` stays 1 — one authored identity
    did this — while `expanded_rows` counts what reached the parquet, and the two coming apart is
    exactly the information a consumer needs. Both are checked against `weights.parquet` itself
    rather than against a literal.
    """
    spec_dir = _two_genotype_expansion(tmp_path / "spec")
    out = tmp_path / "out"
    result = compile_module(spec_dir, out, resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None
    compilation = result.manifest.compilation

    import polars as pl

    weights = pl.read_parquet(out / "weights.parquet")
    assert compilation.expanded_keys == 1
    assert compilation.expanded_rows == weights.height
    # Every row of this module came from the one expansion, so the two counts bracket the artifact.
    assert compilation.expanded_rows == compilation.resolution_subjects

    # And the row the report was about is really there: the authored `TA/TA` beside the *other*
    # locus's reference allele, a well-formed reference homozygote carrying a pathogenic conclusion.
    reference_homozygotes = weights.filter(
        (pl.col("genotype").list.first() == pl.col("ref"))
        & (pl.col("genotype").list.last() == pl.col("ref"))
    )
    assert reference_homozygotes.height == 1
    assert reference_homozygotes["conclusion"].to_list() == ["pathogenic"]


def test_one_warning_per_key_however_many_genotypes_are_authored(tmp_path: Path) -> None:
    """The sentence is about the rsID, so it is published once — with the real row total.

    It used to be emitted inside the per-authored-row loop, so the fixture above put two identical
    copies into `manifest.compilation.warnings`, each saying "expanded to 2 rows" of an artifact that
    had gained four. `manifest.compilation.warnings` is a published surface (RM44), so a count in it
    is an API and a doubled one is a wrong answer, not noise.
    """
    spec_dir = _two_genotype_expansion(tmp_path / "spec")
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None

    expansion = [w for w in result.manifest.compilation.warnings if "maps to 2 loci" in w]
    assert len(expansion) == 1
    assert "expanded to 4 rows from 2 authored genotype(s)" in expansion[0]
    # It also has to say what those rows are — the read-side half of the report.
    assert "do not read a row as a standalone claim about its locus" in expansion[0]


def test_the_counts_are_published_and_move_no_digest(tmp_path: Path) -> None:
    """A manifest field or it is nothing — and it must cost an existing module nothing to gain it.

    `artifact.digest` is a Merkle root over the artifact *files*; `manifest.json` is not one of them.
    Asserting it here rather than reasoning about it is the point: the same spec compiled before and
    after this field existed has to keep its bytes, which is what makes the addition minor-legal
    under Principle 3 rather than merely additive-looking.
    """
    spec_dir = _EXAMPLES / "pathogenic_clinvar"
    out = tmp_path / "out"
    result = compile_module(spec_dir, out, resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None

    written = json.loads((out / "manifest.json").read_text())["compilation"]
    assert written["expanded_keys"] == result.manifest.compilation.expanded_keys
    assert written["expanded_rows"] == result.manifest.compilation.expanded_rows
    assert written["expanded_keys"] > 0

    again = compile_module(spec_dir, tmp_path / "again", resolve_with_ensembl=True)
    assert again.manifest is not None
    assert again.manifest.artifact.digest == result.manifest.artifact.digest


def test_resolution_switched_off_leaves_the_counts_unestablished(tmp_path: Path) -> None:
    """`None`, never `0` — the house tri-state, on a module that certainly does expand.

    `pathogenic_clinvar` has nine one-to-many keys, so `0` here would be a false negative rather than
    an absent measurement, and a catalog reading it would badge the module as expansion-free.
    """
    result = compile_module(
        _EXAMPLES / "pathogenic_clinvar", tmp_path / "out", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert result.manifest is not None
    assert result.manifest.compilation.expanded_keys is None
    assert result.manifest.compilation.expanded_rows is None
