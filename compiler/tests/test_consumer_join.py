"""RM291: join every compiled reference example against an independently normalized VCF, as a consumer does.

Every other check in the suite is internal: it compiles, reverses, recompiles and cross-checks tables
against each other. A consumer's whole operation is different. It calls a VCF with its own tools,
normalized the way callers normalize (left-aligned and trimmed), and joins each record on
`(chrom, pos, ref, alt)`. The +1 indel respelling (RM31) and CCR5-Δ32's dropped carriers (S120) passed
every internal gate; this is the test that would have seen them.

**The fixture** (`assets/consumer_join/`, GRCh38, built 2026-09-27):

- `clinvar_20260627_norm_slice.vcf.gz`: the ClinVar GRCh38 VCF of 2026-06-27, cut to ±100 bp around
  every placed allele-bearing row of the GRCh38 reference examples, INFO reduced to `RS`/`CLNSIG`,
  split to one ALT per record and normalized: `bcftools view -T regions | bcftools reheader --fai
  <fa>.fai | bcftools annotate -x ^INFO/RS,INFO/CLNSIG | bcftools norm -f <Ensembl GRCh38 primary
  assembly> -m -any -c w | bcftools sort`. `norm` realigned 0 of 5,281 records: ClinVar's VCF is
  already in caller form, which is what makes it a fair stand-in for one.
- `grch38_windows.fa.gz`: the same regions from the same FASTA (`samtools faidx -r`), so the test can
  decide whether two spellings are one event without a reference genome on disk.

**The oracle is haplotype equality, never a spelling.** A module row is *expected* to match when some
ClinVar record in the slice, applied to the reference window, spells the same sequence as the row
does. Whether it *does* match is the consumer's exact join. So the expected set is defined without
the normalization under test, and a miss is a row ClinVar carries under a spelling the module does
not use.

**It fails today, on purpose, and the failures are pinned.** `_MISSES_PINNED_TO_RM270` are the rows
RM270 describes (the artifact keys an indel on its source's spelling). `_REF_DISAGREES` held the one
row whose `ref` the reference does not have until RM295 corrected it. Each is an equality, so a row leaving either set, fixed or
newly broken, fails the test, and the sets can only shrink as those items ship.

**Regenerating.** A new reference example with rows outside the windows fails
`test_every_joinable_row_is_inside_the_fixture` by name. Rebuild both files with the commands above
over the new row set, and keep the ClinVar release in the filename.
"""

import gzip
from pathlib import Path

import polars as pl
import pytest
import yaml
from just_dna_compiler.compiler import compile_module

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES = _ROOT / "reference_examples"
_FIXTURE = _ROOT / "assets" / "consumer_join"

#: `(example, table, chrom, start, ref, alt)` rows ClinVar carries at another spelling (RM270). The
#: SHOX 2 bp AG deletion and duplication: Ensembl spells them at `X:634690` (`AGAG>AG`, `AGAG>AGAGAG`),
#: ClinVar and every caller at `X:634689` (`CAG>C`, `C>CAG`).
_MISSES_PINNED_TO_RM270: frozenset[tuple[str, str, str, int, str, str]] = frozenset(
    {
        ("shox_par1", "weights", "X", 634690, "AGAG", "AG"),
        ("shox_par1", "weights", "X", 634690, "AGAG", "AGAGAG"),
    }
)

#: Rows whose `ref` the GRCh38 reference does not have at their `start`. Empty since RM295 moved
#: `cyp2d6_structural`'s CYP2D6*4 row from `22:42127941` (where GRCh38 has `G`) to `22:42128945`.
_REF_DISAGREES: frozenset[tuple[str, str, str, int, str, str]] = frozenset()


def _is_symbolic(ref: str, alt: str) -> bool:
    """A symbolic allele (`<DEL:4977>`, ref `N`) names no sequence, so no exact join can place it."""
    return ref.upper() == "N" or alt.startswith("<") or ref.startswith("<")


def _windows() -> list[tuple[str, int, str]]:
    windows: list[tuple[str, int, str]] = []
    name, parts = None, []
    with gzip.open(_FIXTURE / "grch38_windows.fa.gz", "rt") as handle:
        lines = handle.read().splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            if name is not None:
                windows.append((*name, "".join(parts)))
            chrom, span = line[1:].rsplit(":", 1)
            name, parts = (chrom, int(span.split("-")[0])), []
        else:
            parts.append(line.upper())
    if name is not None:
        windows.append((*name, "".join(parts)))
    return windows


def _haplotype(windows, chrom: str, pos: int, ref: str, alt: str) -> tuple | str | None:
    """The window with the record applied, `"ref_disagrees"`, or `None` when no window holds it."""
    for w_chrom, first, seq in windows:
        if w_chrom == chrom and first <= pos and pos + len(ref) - 1 < first + len(seq):
            i = pos - first
            if seq[i : i + len(ref)] != ref:
                return "ref_disagrees"
            return (w_chrom, first, seq[:i] + alt + seq[i + len(ref) :])
    return None


@pytest.fixture(scope="module")
def join(tmp_path_factory: pytest.TempPathFactory) -> dict[str, set]:
    """Compile every GRCh38 example, join each allele row, and sort the rows by outcome."""
    windows = _windows()
    records: set[tuple[str, int, str, str]] = set()
    carried: set[tuple] = set()
    with gzip.open(_FIXTURE / "clinvar_20260627_norm_slice.vcf.gz", "rt") as handle:
        vcf_lines = handle.read().splitlines()
    for line in vcf_lines:
        if line.startswith("#"):
            continue
        chrom, pos, _id, ref, alt = line.split("\t")[:5]
        record = (chrom, int(pos), ref.upper(), alt.upper())
        records.add(record)
        hap = _haplotype(windows, *record)
        if isinstance(hap, tuple):
            carried.add(hap)

    outcome: dict[str, set] = {k: set() for k in ("matched", "missed", "ref_disagrees", "outside")}
    out = tmp_path_factory.mktemp("consumer_join")
    for example in sorted(p for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").is_file()):
        spec = yaml.safe_load((example / "module_spec.yaml").read_text(encoding="utf-8")) or {}
        if (spec.get("genome_build") or "GRCh38") != "GRCh38":
            continue  # the slice is GRCh38; a GRCh37 example has nothing to join against here
        compile_module(example, out / example.name)
        for parquet in sorted((out / example.name).glob("*.parquet")):
            schema = pl.read_parquet_schema(parquet)
            alt_column = "alts" if "alts" in schema else ("alt" if "alt" in schema else None)
            if alt_column is None or not {"chrom", "start", "ref"} <= set(schema):
                continue
            for row in pl.read_parquet(parquet, columns=["chrom", "start", "ref", alt_column]).iter_rows():
                chrom, start, ref, alts = row
                if chrom is None or start is None or not ref or not alts:
                    continue
                for alt in alts if isinstance(alts, list) else str(alts).split(","):
                    if not alt or _is_symbolic(ref, alt):
                        continue
                    key = (example.name, parquet.stem, chrom, int(start), ref.upper(), alt.upper())
                    hap = _haplotype(windows, chrom, int(start), ref.upper(), alt.upper())
                    if hap is None:
                        outcome["outside"].add(key)
                    elif hap == "ref_disagrees":
                        outcome["ref_disagrees"].add(key)
                    elif hap in carried:
                        exact = (chrom, int(start), ref.upper(), alt.upper()) in records
                        outcome["matched" if exact else "missed"].add(key)
    return outcome


def test_every_joinable_row_is_inside_the_fixture(join: dict[str, set]) -> None:
    """A row outside every window was never tested: regenerate the fixture rather than skip it."""
    assert join["outside"] == set(), f"rebuild assets/consumer_join for: {sorted(join['outside'])}"


def test_every_row_clinvar_carries_joins_except_the_pinned_rm270_set(join: dict[str, set]) -> None:
    """The consumer's join. Equality with the pinned set: fixed or newly broken, either fails here."""
    assert join["matched"], "the join matched nothing, so it is not testing a join"
    assert join["missed"] == _MISSES_PINNED_TO_RM270


def test_no_row_states_a_ref_the_reference_lacks(
    join: dict[str, set],
) -> None:
    assert join["ref_disagrees"] == _REF_DISAGREES
