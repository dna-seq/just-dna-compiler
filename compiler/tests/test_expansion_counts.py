"""Both halves of the expansion answer: the artifact-level counts (S33) and the row-level pair (RM87).

A one-to-many rsID is paired with every locus it resolves to, so an authored genotype becomes N rows
of which **one** can match. The other N-1 are well-formed: correct grammar, the module's own
conclusion, a locus whose alleles cannot carry that genotype. A reporting consumer read 2,579 of them
as reference genotypes their subject carried, caught before rendering — and could not have known from
the artifact that any such row was there, because nothing in `weights.parquet` distinguished an
expanded row from an authored one.

The expansion itself is not the defect and is not changed here (COMPILER.md § Resolution says why, and
Principle 7 forbids the obvious prune). Two things were added instead, and the second half of this
file is the one nobody had written:

* `manifest.compilation.expanded_keys` / `expanded_rows` (0.6, S33) answer *does this module contain
  such rows at all* — an artifact-level fact, whose own docstring says it deliberately does not
  substitute for the row-level one.
* `VariantRow.locus_index` / `locus_count` (0.6, RM87) answer it **while holding one row**, which is
  the position a consumer reads from. `locus_count > 1` is the predicate; `locus_index` lines the row
  up with its `resolution.csv` row. Neither alone is enough — `locus_index` is `0` on a non-expanded
  row *and* on the first member of every expansion — and both are `exclude=True`, so no
  `content_signature` moves.

Every expectation is derived at runtime — from the module's own `resolution.csv`, from another
manifest field, or from a fixture this file writes and can therefore count. Nothing is a number read
off a data dump.
"""

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module
from just_dna_format.base import authored_field_names
from just_dna_format.integrity import content_signature as signature_over_rows
from just_dna_format.spec import VariantRow

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


# ── RM87: the row-level marker ──────────────────────────────────────────────────────────────────
#
# The counts above say *whether*; these say *which*. Written against real corpus modules rather than
# only the fixture, because the shape that matters — several authored genotypes over several loci —
# exists in `pathogenic_clinvar` (nine one-to-many keys) and `hboc_palb2` (two) and had never been
# asserted anywhere: the single direct assertion in the suite was a one-locus `locus_index == "0"`.

#: The columns that identify one authored row, so its expansion members group together. `rsid` alone
#: is not enough — two authored genotypes at one rsID each expand onto the same loci, and their
#: sequences are independent `0..N-1` runs rather than one `0..2N-1`.
_MEMBER_GROUP = ("rsid", "genotype", "authored_ident")


def _expansion_groups(weights: pl.DataFrame) -> dict[tuple, list[dict]]:
    """Weights rows grouped by the authored row they came from, expanded members only."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in weights.iter_rows(named=True):
        if row["locus_count"] <= 1:
            continue
        key = tuple(
            tuple(row[c]) if isinstance(row[c], list) else row[c] for c in _MEMBER_GROUP
        )
        groups[key].append(row)
    return groups


def _expanding_examples() -> list[Path]:
    """Corpus modules whose injected table resolves some key onto more than one locus."""
    found = [d for d in _example_dirs() if _multi_locus_keys(d)]
    assert found, "the corpus must keep a one-to-many module or these tests prove nothing"
    return found


@pytest.mark.parametrize("spec_dir", _expanding_examples(), ids=lambda d: d.name)
def test_every_expanded_authored_row_carries_a_complete_zero_to_n_sequence(
    spec_dir: Path, tmp_path: Path
) -> None:
    """`locus_index` covers `0..N-1` exactly once per expanded authored row, and `locus_count` is N.

    Set equality rather than a count, so a sequence that repeats an ordinal or skips one fails even
    where the length happens to come out right. The expected N is read off the group itself — the
    number of members the compiler actually emitted — so nothing here is a literal.
    """
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet")

    groups = _expansion_groups(weights)
    assert groups, f"{spec_dir.name} was selected as an expanding module and emitted no marked rows"
    for key, members in groups.items():
        counts = {m["locus_count"] for m in members}
        assert counts == {len(members)}, f"{key}: locus_count {counts} for {len(members)} members"
        assert {m["locus_index"] for m in members} == set(range(len(members))), key
        # The members really are different loci — the marker would be worthless on duplicate rows.
        assert len({(m["chrom"], m["start"], m["ref"]) for m in members}) == len(members), key

    # And the row-level marker agrees with the artifact-level counts it does not substitute for.
    assert result.manifest is not None
    assert result.manifest.compilation.expanded_keys is not None
    marked = weights.filter(pl.col("locus_count") > 1)
    assert marked.height == result.manifest.compilation.expanded_rows


@pytest.mark.parametrize("spec_dir", _example_dirs(), ids=lambda d: d.name)
def test_a_row_that_was_not_expanded_says_exactly_that(spec_dir: Path, tmp_path: Path) -> None:
    """`locus_count == 1` ⟺ `locus_index == 0`, on every module including the ones that never expand.

    This is the half `locus_index` alone cannot express, and the reason the default is `1` and not
    `0`: a reader holding one row must be able to separate "not expanded" from "first member of an
    expansion", and a zero default would make the predicate read `> 1 or == 0`.
    """
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    weights_path = tmp_path / "out" / "weights.parquet"
    if not weights_path.is_file():
        return  # a table-only module — the columns live on the SNP core
    weights = pl.read_parquet(weights_path)

    unexpanded = weights.filter(pl.col("locus_count") == 1)
    assert unexpanded["locus_index"].to_list() == [0] * unexpanded.height
    # Nothing may claim membership of a zero-member expansion, or an ordinal outside its own run.
    assert weights.filter(pl.col("locus_count") == 0).height == 0
    assert weights.filter(pl.col("locus_index") >= pl.col("locus_count")).height == 0


def test_the_sequence_survives_compile_reverse_compile(tmp_path: Path) -> None:
    """The obligation P7 gained with the columns, on the corpus module that really has the shape.

    `pathogenic_clinvar` carries nine one-to-many keys. Reverse collapses each expansion back to the
    single authored row it was written as and rebuilds `resolution.csv` from the parquet, so the
    second compile has to re-derive the whole sequence from a table it wrote itself. Comparing the
    two frames column-for-column is stronger than comparing digests alone: it says *which* column
    would have moved.
    """
    spec_dir = _EXAMPLES / "pathogenic_clinvar"
    first = compile_module(spec_dir, tmp_path / "a1", resolve_with_ensembl=True)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2", resolve_with_ensembl=True)
    assert second.success, second.errors

    w1 = pl.read_parquet(tmp_path / "a1" / "weights.parquet")
    w2 = pl.read_parquet(tmp_path / "a2" / "weights.parquet")
    assert w1["locus_index"].to_list() == w2["locus_index"].to_list()
    assert w1["locus_count"].to_list() == w2["locus_count"].to_list()
    assert _expansion_groups(w1).keys() == _expansion_groups(w2).keys()
    assert max(w1["locus_count"].to_list()) > 1, "the fixture must actually expand"
    assert first.manifest.artifact.digest == second.manifest.artifact.digest


@pytest.mark.parametrize("spec_dir", _expanding_examples(), ids=lambda d: d.name)
def test_reverse_prefers_the_stored_column_and_the_recompute_agrees_with_it(
    spec_dir: Path, tmp_path: Path
) -> None:
    """Both halves of the P3 fallback in one comparison, on the real reverse path.

    `_write_resolution_csv` reads `locus_index` off the parquet where it is present and falls back to
    counting by encounter order, because an artifact compiled before 0.6 has no such column and has
    to keep reversing. Stripping the column from a real `weights.parquet` is what a pre-0.6 artifact
    looks like, so reversing the same artifact twice — once with the column, once without —
    exercises the stored path, the fallback path, and the claim that they agree.

    The agreement is not free: the recompute works only because the weights rows happen to be sorted
    on the ordinal. That dependency was silent until this comparison existed.
    """
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    weights_path = tmp_path / "out" / "weights.parquet"
    reverse_module(tmp_path / "out", tmp_path / "rev_stored")

    stripped = pl.read_parquet(weights_path).drop("locus_index", "locus_count")
    assert "locus_index" not in stripped.columns
    stripped.write_parquet(weights_path)
    reverse_module(tmp_path / "out", tmp_path / "rev_recomputed")

    stored = (tmp_path / "rev_stored" / "resolution.csv").read_text(encoding="utf-8")
    recomputed = (tmp_path / "rev_recomputed" / "resolution.csv").read_text(encoding="utf-8")
    assert stored == recomputed
    # And the comparison is about something: this module's table really does carry a non-zero index.
    indices = {row["locus_index"] for row in csv.DictReader(io.StringIO(stored))}
    assert indices > {"0"}


def _divergent_expansion(spec_dir: Path) -> Path:
    """One rsID, three loci, two authored genotypes that reach **different** hostable sets.

    Built from `pathogenic_clinvar`'s `rs281864532`, the module's own three-way case: this repo's
    notes record it as `G>GT`, `GT>G` **and** `GTT>G` under one rsID, and the example's injected table
    carries the first two. The third is added here with the middle `locus_index`, which is what makes
    the sets diverge in the order that matters:

    * `G/GT` — the example's own authored genotype — cannot be hosted by `GTT>G`: re-anchoring moves
      an indel but never changes how many bases it adds or removes, so a 1 bp insertion beside a 2 bp
      deletion is a confident `False`. Its expansion is the two outer loci, stamped `0, 1`.
    * `G/G` names only `G`, which every one of the three loci has, so its expansion is all three,
      stamped `0, 1, 2`.

    Reverse emits each locus once, so `GTT>G` arrives carrying ordinal 1 — already spent by the other
    genotype's second member. `best_effort`, necessarily: dropping a locus appends a strict error.
    """
    source = _EXAMPLES / "pathogenic_clinvar"
    rsid = "rs281864532"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "module_spec.yaml").write_text(
        (source / "module_spec.yaml").read_text().replace("pathogenic_hbb", "divergent_probe")
    )
    variants = (source / "variants.csv").read_text().splitlines()
    authored = [variants[0]] + [line for line in variants if line.startswith(f"{rsid},")]
    assert len(authored) == 2, "the fixture assumes the example authors this rsID exactly once"
    authored.append(authored[1].replace(",G/GT,", ",G/G,"))
    (spec_dir / "variants.csv").write_text("\n".join(authored) + "\n")

    resolution = (source / "resolution.csv").read_text().splitlines()
    header = resolution[0].split(",")
    loci = [line.split(",") for line in resolution if line.startswith(f"{rsid},")]
    assert len(loci) == 2, "the fixture assumes this rsID resolves onto exactly two loci"
    third = list(loci[0])
    for column, value in (("ref", "GTT"), ("alts", "G"), ("locus_index", "1"), ("vrs_id", "")):
        third[header.index(column)] = value
    # The added locus takes the middle ordinal; the example's `GT>G` moves out to 2. `_sorted_loci`
    # orders on `locus_index` first, so this is what puts the rejected locus between the survivors.
    loci[1][header.index("locus_index")] = "2"
    rows = [",".join(r) for r in (loci[0], third, loci[1])]
    (spec_dir / "resolution.csv").write_text("\n".join([resolution[0], *rows]) + "\n")

    (spec_dir / "studies.csv").write_text(f"rsid,chrom,start,ref,pmid\n{rsid},,,,29165669\n")
    literature = (source / "literature.csv").read_text().splitlines()
    (spec_dir / "literature.csv").write_text(
        "\n".join([literature[0], *(x for x in literature if x.startswith("29165669,"))]) + "\n"
    )
    return spec_dir


def test_a_reversed_table_never_files_two_loci_under_one_ordinal(tmp_path: Path) -> None:
    """The uniqueness `ResolutionRow` documents, on the one shape that can break it.

    `locus_index` is inside `RESOLUTION_FACT_FIELDS`, and the schema tier's contract is several rows
    sharing a `variant_key` with **distinct** ordinals — so a duplicate is a malformed signed fact,
    not a cosmetic slip. Unconditional prefer-stored produces one here, because the stamp counts
    within a single authored row's hostable set while this writer emits each locus once. Nothing in
    the corpus has the shape, which is exactly why the guard needs its own fixture.
    """
    spec_dir = _divergent_expansion(tmp_path / "spec")
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors

    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet")
    # The premise: the two authored genotypes really did reach different-sized expansions.
    assert set(weights["locus_count"].to_list()) == {2, 3}

    reverse_module(tmp_path / "out", tmp_path / "rev")
    rows = list(csv.DictReader(io.StringIO((tmp_path / "rev" / "resolution.csv").read_text())))
    per_key: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        per_key[row["variant_key"]].append(row["locus_index"])
    for key, indices in per_key.items():
        assert len(set(indices)) == len(indices), f"{key} files two loci under one ordinal: {indices}"
        assert sorted(int(i) for i in indices) == list(range(len(indices))), key

    # The table still recompiles, and its own reverse is collision-free too. `artifact.digest` is
    # deliberately **not** asserted across this round trip and the guard does not change that: the
    # reversed table renumbers the loci relative to the injected one, so the second compile sorts the
    # expansion differently. That is the pre-existing consequence of dropping a locus, which is why
    # dropping one appends a strict error saying the compile is no longer reproducible from the
    # injected table — the same numbers come out of the encounter-order counter alone.
    again = compile_module(tmp_path / "rev", tmp_path / "out2", resolve_with_ensembl=True)
    assert again.success, again.errors
    reverse_module(tmp_path / "out2", tmp_path / "rev2")
    second = list(csv.DictReader(io.StringIO((tmp_path / "rev2" / "resolution.csv").read_text())))
    per_key_again: dict[str, list[str]] = defaultdict(list)
    for row in second:
        per_key_again[row["variant_key"]].append(row["locus_index"])
    assert all(len(set(v)) == len(v) for v in per_key_again.values())


def test_a_blank_stamped_cell_is_accepted_and_overwritten(tmp_path: Path) -> None:
    """The accept-and-overwrite promise has to survive the loader, not just the constructor.

    `load_csv_rows` turns an empty cell into `None` **and keeps the key**, so a bare `int` annotation
    would make a blank `locus_count` column an `Input should be a valid integer` — a generic type
    error where the sibling stamped columns give an author their value back. `variant_key` has been
    accepted-and-overwritten since 0.5 on the no-foot-gun rule and these two match it.
    """
    from just_dna_compiler.compiler import load_csv_rows

    path = tmp_path / "variants.csv"
    path.write_text(
        "rsid,genotype,state,conclusion,locus_index,locus_count\n"
        "rs1801133,A/G,risk,c,,\n"
        "rs4988235,C/T,protective,c,7,9\n",
        encoding="utf-8",
    )
    rows, errors, _ = load_csv_rows(path, VariantRow, "variants.csv")
    assert errors == []
    assert [(r.locus_index, r.locus_count) for r in rows] == [(0, 1), (0, 1)]


def test_the_marker_is_outside_content_signature() -> None:
    """The load-bearing assertion: no already-published module's authored identity moves.

    Asserted where it can actually fail — over the same rows with and without a stamp — rather than
    by re-reading `exclude=True`. A plain (non-excluded) field here would move `content_signature` on
    every SNP-core module ever published, to record something no human authored.
    """
    authored = VariantRow(rsid="rs1801133", genotype="A/G", state="risk", conclusion="c")
    stamped = authored.model_copy(update={"locus_index": 2, "locus_count": 5})
    assert (stamped.locus_index, stamped.locus_count) == (2, 5)
    assert signature_over_rows({"variants.csv": [authored]}) == signature_over_rows(
        {"variants.csv": [stamped]}
    )

    # Neither column is offered to an author, in either of the two surfaces that decide that.
    assert {"locus_index", "locus_count"}.isdisjoint(authored_field_names(VariantRow))
    assert {"locus_index", "locus_count"}.isdisjoint(stamped.model_dump())

    # An authored cell is accepted and overwritten, the same treatment `variant_key` gets. The fields
    # exist on the model, so `extra="forbid"` cannot see the column, and nothing else would ever
    # correct it — a non-expanded row is marked by the defaults, with no stamp-at-load pass.
    hand_written = VariantRow(
        rsid="rs1801133", genotype="A/G", state="risk", conclusion="c",
        locus_index=7, locus_count=9,
    )
    assert (hand_written.locus_index, hand_written.locus_count) == (0, 1)


def test_the_columns_reach_the_parquet_and_not_a_reversed_variants_csv(tmp_path: Path) -> None:
    """Compiler-managed means materialized *and* never written back — both directions, one test.

    The house rule is that an authored column is three touch points with reverse's `fieldnames` list
    as the one that gets missed. These are not authored, so the rule cuts the other way: re-emitting
    them would put a compiler-stamped value into `variants.csv` as if a human had typed it, which is
    exactly what `authored_ident` exists to prevent.
    """
    spec_dir = _EXAMPLES / "pathogenic_clinvar"
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors

    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet")
    assert weights.schema["locus_index"] == pl.UInt32
    assert weights.schema["locus_count"] == pl.UInt32

    reverse_module(tmp_path / "out", tmp_path / "rev")
    header = next(csv.reader(io.StringIO((tmp_path / "rev" / "variants.csv").read_text())))
    assert {"locus_index", "locus_count"}.isdisjoint(header)
    # The authored identity of the reversed module is the authored identity of the original.
    assert content_signature(spec_dir) == content_signature(tmp_path / "rev")


def _same_ref_par_expansion(spec_dir: Path) -> tuple[Path, str, str]:
    """A two-locus key whose loci share a `ref` — the shape a `ref`-spelling guard passes through.

    Built from `shox_par1`, whose committed `resolution.csv` holds ten single-locus rsIDs on chrX and
    therefore instantiates nothing: PAR twinning is what `enrich --keep-par-twin` records, and the
    example ships the default (X only). So the twin is written here, from the example's own row and
    through `par_partner` rather than a typed-in Y coordinate.

    **Why it is worth a fixture of its own.** The corpus's other expansion (`pathogenic_clinvar`'s
    `rs1554917888`, `T>TA` beside `TA>T`) differs in `ref`, so every existing assertion here would
    survive an expansion that deduped on `(chrom, start, ref)` — and the claim
    INTEGRATION_0_6 § 3 makes to a consumer, that a `ref`-spelling mitigation misses same-`ref`
    expansions, had no instance anywhere in this repo until a consumer went looking for one (S40).

    `vrs_id` is cleared on both loci: a VA does not encode `ref`, so the X row's ids are genuinely
    wrong for a Y position and the check refuses them — correctly. Empty is the honest cell, and this
    fixture is about `locus_count`, not about identity.
    """
    from just_dna_format.vrs import par_partner

    source = _EXAMPLES / "shox_par1"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "module_spec.yaml").write_text(
        (source / "module_spec.yaml").read_text().replace("shox_par1", "par_twin_probe")
    )

    rows = list(csv.DictReader(io.StringIO((source / "resolution.csv").read_text())))
    grounded = {r["rsid"] for r in csv.DictReader(io.StringIO((source / "studies.csv").read_text()))}
    x = next(r for r in rows if r["chrom"] == "X" and r["rsid"] in grounded)
    partner = par_partner(x["chrom"], int(x["start"]), build=x["genome_build"])
    assert partner is not None, "the example's row must sit in a pseudoautosomal region"
    y = dict(x, chrom=partner[0], start=str(partner[1]), locus_index="1", vrs_id="")
    x = dict(x, locus_index="0", vrs_id="")
    assert x["ref"] == y["ref"], "the point of the fixture is that the two loci agree on ref"

    fieldnames = list(rows[0])
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows([x, y])
    (spec_dir / "resolution.csv").write_text(buf.getvalue())

    variants = (source / "variants.csv").read_text().splitlines()
    authored = [variants[0]] + [ln for ln in variants if ln.startswith(f"{x['rsid']},")]
    assert len(authored) == 2, "the example must author this rsID exactly once"
    (spec_dir / "variants.csv").write_text("\n".join(authored) + "\n")

    studies = (source / "studies.csv").read_text().splitlines()
    kept = [ln for ln in studies if ln.startswith(f"{x['rsid']},")]
    (spec_dir / "studies.csv").write_text("\n".join([studies[0], *kept]) + "\n")
    (spec_dir / "licensing.csv").write_text((source / "licensing.csv").read_text())
    return spec_dir, x["ref"], x["rsid"]


def test_two_loci_sharing_a_ref_still_count_as_two(tmp_path: Path) -> None:
    """The same-`ref` expansion, which a `ref`-spelling guard cannot see and `locus_count` can.

    Both halves are asserted against each other rather than against a written-down number: the rows
    carry exactly one distinct `ref` between them, *and* `locus_count` reads 2 on every one. A
    dedup on `(chrom, start, ref)` would keep the first assertion true and break the second, which is
    the failure this pins.
    """
    spec_dir, ref, rsid = _same_ref_par_expansion(tmp_path / "spec")
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors

    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet").filter(pl.col("rsid") == rsid)
    assert set(weights["ref"].to_list()) == {ref}, "the two loci must be indistinguishable by ref"
    assert set(weights["locus_count"].to_list()) == {2}
    assert sorted(weights["locus_index"].to_list()) == [0, 1]
    assert set(weights["chrom"].to_list()) == {"X", "Y"}, "one place, two contigs"
    assert result.manifest is not None
    assert result.manifest.compilation.expanded_keys == 1
    assert result.manifest.compilation.expanded_rows == 2
