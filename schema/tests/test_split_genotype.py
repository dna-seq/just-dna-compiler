"""The public genotype split (S30), pinned against the corpus it has to keep agreeing with.

The rule lives in three places that must agree — the validator's grammar, the compiler's materializer,
and every consumer reading a 0.4-family table — and the third had only prose to work from. A consumer
re-derived it twice, in opposite directions, and neither round involved a failing run: a
reimplementation that sorts raises nothing, it just matches a quietly larger set on phased data.

So these assertions are the deciding argument made durable, and they are checked against what the
compiler actually writes rather than against a restatement of it.
"""

import csv
import re
from pathlib import Path

import pytest
from just_dna_format.alleles import split_genotype
from just_dna_format.spec import VariantRow

REFERENCE_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def test_the_authored_order_survives_and_a_phased_pair_is_not_sorted() -> None:
    """The property the whole report turns on. `weights.parquet` stores this list verbatim, so a
    consumer that sorts gives one artifact two spellings of one genotype."""
    assert split_genotype("G|A") == ["G", "A"]
    assert split_genotype("G/A") == ["G", "A"]
    assert split_genotype("A|G") == ["A", "G"]
    # Sorting would collapse the first two into the third, which is exactly the larger match set.
    assert split_genotype("G|A") != split_genotype("A|G")


def test_a_hemizygous_cell_is_one_allele_not_a_padded_pair() -> None:
    """How every haploid contig in the corpus is authored — `mt_heteroplasmy` writes `G`, not `G/G`.

    Padding it to a pair would invent a homozygous diploid call on a contig that has no second copy.
    """
    assert split_genotype("G") == ["G"]
    assert split_genotype("<DEL:4977>") == ["<DEL:4977>"]


def test_it_splits_and_does_not_judge() -> None:
    """Contract: a *validated* cell in, alleles out. Members come back verbatim, whatever they spell —
    `*` (RM59) and symbolic alleles (RM5) included, since a split is not a grammar."""
    assert split_genotype("*/T") == ["*", "T"]
    assert split_genotype("<DEL:1500>/A") == ["<DEL:1500>", "A"]


def test_dropping_empties_is_not_a_widening_of_what_the_models_accept() -> None:
    """`|A|G` splits cleanly here and is **refused** by the model (RM67's leading-separator divergence).

    The split being total over any string is what makes it safe to call anywhere; it decides nothing
    about legality, and the guard that does is untouched by it.
    """
    assert split_genotype("|A|G") == ["A", "G"]
    with pytest.raises(ValueError):
        VariantRow(rsid="rs1801133", genotype="|A|G", state="risk", conclusion="x")


def test_the_compiler_reads_this_leaf_and_not_a_copy_of_it() -> None:
    """Three copies of the regex existed — `compiler.py`, `resolution.py`, and the consumer's engine.

    Two of them are ours, and two that agree today do not fail when they drift; they stop matching.
    """
    from just_dna_compiler import compiler as compiler_module
    from just_dna_compiler import resolution as resolution_module

    assert compiler_module._split_genotype is split_genotype
    assert resolution_module.split_genotype is split_genotype


@pytest.mark.parametrize(
    "spec_dir", sorted(p.name for p in REFERENCE_EXAMPLES.iterdir() if (p / "variants.csv").exists())
)
def test_every_authored_genotype_in_the_corpus_splits_to_what_its_separators_say(spec_dir: str) -> None:
    """Ground truth computed at runtime from the real corpus, never a transcribed expectation.

    The independent expectation is the count of separators the cell carries, which is the one thing a
    reader can see without knowing this function: an `n`-separator cell names `n + 1` alleles.
    """
    rows = list(csv.DictReader((REFERENCE_EXAMPLES / spec_dir / "variants.csv").open()))
    assert rows, f"{spec_dir} carries no variant rows"
    for row in rows:
        cell = row["genotype"]
        alleles = split_genotype(cell)
        assert alleles == [a for a in re.split(r"[/|]", cell) if a]
        assert len(alleles) == cell.count("/") + cell.count("|") + 1
        assert "".join(alleles) == re.sub(r"[/|]", "", cell)
