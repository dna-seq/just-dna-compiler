"""STRchive — the repeat-locus catalogue, read for the two halves it is split into (RM165).

`repeat_alleles.csv` was the one binning kind nothing in this tier had ever asked a question about.
STRchive (`dashnowlab/STRchive`, MIT) publishes ~82 tandem-repeat disease loci with coordinates,
motifs, the motif structure, and three bands per locus — `benign_*`, `intermediate_*`,
`pathogenic_*`. The item that adopts it **splits the source by column**: the identity half is drafted
(`strchive_draft`), and the band half is *checked here and never written*.

**Why the bands are checked rather than drafted, measured on both corpus modules.**

* `reference_examples/htt_repeat_expansion` — the source agrees where it speaks. STRchive gives
  `benign 6–26` and `intermediate 27–35`; the shipped table gives `6,26` and `27,35`, independently
  authored. It also splits STRchive's single pathogenic band at 40, which is the reduced-penetrance /
  full-penetrance line, and STRchive states no boundary there.
* `reference_examples/fmr1_cgg_repeat` — the source is one band coarser exactly where that matters.
  STRchive gives `intermediate 45–200`; the module states `45–54` and `55–200`, and **55 is the
  premutation threshold**. Drafting the three bands straight would erase a clinically load-bearing
  line.

So both corpus modules are *finer* than the catalogue, in two different places, for two different
reasons. A drafting provider would write the source's tiling as the answer; this reports the
difference and leaves the author to keep their own line or to move it.

**`pathogenic_max` is never emitted as `measure_max`, and that is the sharpest of the refusals.**
STRchive's HTT `pathogenic_max` is 250; the module leaves the top band open. A catalogue's
`pathogenic_max` is the largest allele the literature reports — an observation, not a clinical bound.
Written into `measure_max`, a 300-repeat allele would match **no bin at all**, silently, `--strict`
included, which is the exact silence RM55 shipped a loud warning about. The check *reports* the extra
ceiling as its own finding kind; nothing here ever writes it.

**Never escalates under `--strict`.** Two expert bodies drawing a threshold in different places is a
scientific difference, not a defect in the module, and failing a compile over it would make the format
arbitrate between its own authorities — the rule `enrich_pgx`'s function-status check and the ClinVar
`clin_sig` cross-check already follow. `strict` still refuses a *structural* failure: a
`repeat_alleles.csv` that will not load raises in both modes.

**No live route, and no `SourceRow`.** The catalogue is a single small JSON file, so this follows
`acmg`'s shape rather than `pgx`'s: an operator builds a snapshot with `strchive build` (or points at
a downloaded `STRchive-loci.json`) and passes it in. Nothing from STRchive lands in the module on this
path — the bands were authored by a human before this ran, and `sources.csv` exists to account for
what a module *carries*, which is why `acmg` and `check-identifiers` record no terms either. The
drafting half does carry the source's data, and it writes a `SourceRow`.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows

# `_bin_groups` is private and imported anyway, deliberately. The group key it builds —
# `_KEY_FIELDS + (trait_efo_id,)`, with `unresolved` rows dropped — is the partition the overlap rule
# is enforced over, and its own docstring says why a second copy is the thing to avoid: a check that
# grouped differently would be answering this question against a partition nothing else uses. The
# alternative was a one-line public alias in `binning`, and this round's items are barred from editing
# `schema/` beyond flipping their own attestation member.
from just_dna_format.binning import (
    MeasureBinRow,
    RepeatAlleleRow,
    _bin_groups,
    format_group_key,
    resolve_tiling,
)
from just_dna_format.manifest import VerificationRecord

from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    STRCHIVE_CATALOGUE_FILENAME,
    resolve_strchive_reference,
)
from just_dna_enricher.verification import examples, ran, record_verification, skipped

logger = logging.getLogger(__name__)

#: The name this source is spelled with everywhere — the verification record's `source`, the licence
#: row the drafting half writes, and the snapshot's `release.json`.
SOURCE_NAME = "strchive"

#: The catalogue file inside a built snapshot, and the name the upstream repository gives it.

#: The provenance file a built snapshot carries beside the catalogue.

#: The authored table this check reads. One name rather than a `_TABLE_KINDS` lookup, because the
#: check is *about* this kind: `RepeatAlleleRow` is the only binning kind a repeat catalogue speaks to.
REPEAT_ALLELES_CSV = "repeat_alleles.csv"

#: STRchive's three bands, in axis order. The names are the source's own column prefixes, and the
#: order is what makes "the band a boundary falls inside" answerable.
BAND_NAMES: tuple[str, ...] = ("benign", "intermediate", "pathogenic")


class StrchiveError(RuntimeError):
    """A STRchive catalogue could not be read, or an authored table could not be loaded."""


class StrchiveUnavailable(StrchiveError):
    """No catalogue was provisioned, so the comparison could not be put at all."""


@dataclass(frozen=True)
class Band:
    """One closed-ish interval on the repeat-count axis, from either side of the comparison.

    `lo`/`hi` are `None` for *open*, never for zero — absent bounds are open, which is the same
    reading `MeasureBinRow` gives them. `label` names where the interval came from: a STRchive band
    name on the source side, and the authored `phenotype` (or the group key) on the module's.
    """

    label: str
    lo: float | None
    hi: float | None

    def divides(self, value: float, *, tiling: str | None = None) -> bool:
        """Would a bin starting at `value` divide this interval — is there interval on both sides?

        The predicate behind "the source states no boundary here". An absent bound is **open**, so it
        never excludes: a bin open below has interval below every value, which is the reading that
        keeps a division inside an unbounded bin reportable rather than silently dropped.

        The **upper** end is where the tiling matters (`@dense-bin-boundary`). Under quantised tiling
        a cut at this interval's own `hi` leaves the top grid point as a bin of its own, which is a
        real division; under continuous it leaves a degenerate point, which is not — it is the same
        fact as the two ceilings differing, and reporting it as a lost boundary as well would say one
        thing twice. STRchive states its bands in the quantised form, so the default is that reading.
        """
        if self.lo is not None and value <= self.lo:
            return False
        if self.hi is None:
            return True
        return value < self.hi if tiling == "continuous" else value <= self.hi

    def __str__(self) -> str:
        lo = "open" if self.lo is None else _number(self.lo)
        hi = "open" if self.hi is None else _number(self.hi)
        return f"{self.label} [{lo}, {hi}]"


@dataclass(frozen=True)
class StrchiveLocus:
    """One catalogue record, reduced to what the two halves of this item read.

    Deliberately not the whole record. `evidence`, the HPO terms and the cross-references are real and
    are not parsed, because nothing here emits them — a field carried and never used is the dead
    weight this tree refactors out rather than keeps.
    """

    locus_id: str
    gene: str
    #: The pathogenic motif as the *reference* spells it, and as the *gene* spells it. Both, because a
    #: minus-strand locus is authored either way and the module's `repeat_unit` is one motif string
    #: with no orientation column to say which — so matching on the union is the only honest join.
    reference_motifs: tuple[str, ...]
    gene_motifs: tuple[str, ...]
    bands: tuple[Band, ...]
    mondo: tuple[str, ...]
    ref_copies: float | None
    #: `(motif, count, type)` triples, present on some loci and `[]` on others. Carried for the
    #: drafting half's report — this is the RM66 evidence, and no authored column holds it.
    locus_structure: tuple[tuple[str, int | None, str], ...]
    disease: str | None

    @property
    def motifs(self) -> tuple[str, ...]:
        """Every spelling of this locus's pathogenic motif, de-duplicated, reference first."""
        seen: list[str] = []
        for motif in (*self.reference_motifs, *self.gene_motifs):
            if motif and motif not in seen:
                seen.append(motif)
        return tuple(seen)


@dataclass(frozen=True)
class StrchiveCatalogue:
    """A parsed catalogue plus what it was read from, so a record can say which release it compared."""

    loci: tuple[StrchiveLocus, ...]
    dataset: str | None = None
    source_url: str | None = None
    path: Path | None = None

    def by_gene_and_motif(self) -> dict[tuple[str, str], list[StrchiveLocus]]:
        """`(gene, motif)` → every locus claiming it, in file order.

        A **list**, not a locus. `ARX` carries two loci and `HOXA13` three, all keyed `(gene, 'NGC')`
        — a real fan-out in the published file. Picking one would make the comparison depend on file
        order, so the caller reports the contested key and compares nothing (`@multiplicity-is-a-finding`).
        """
        index: dict[tuple[str, str], list[StrchiveLocus]] = {}
        for locus in self.loci:
            for motif in locus.motifs:
                index.setdefault((locus.gene, motif), []).append(locus)
        return index

    def genes(self) -> frozenset[str]:
        return frozenset(locus.gene for locus in self.loci)


def _number(value: float) -> str:
    """A bound as a reader would write it — `26`, not `26.0`.

    Same normalization `binning.format_group_key` applies to a group key, for the same reason: these
    sentences reach `verification.json`, which is a hashed input, so a whole number that renders two
    ways would move a module's bytes for nothing.
    """
    return str(int(value)) if float(value).is_integer() else str(value)


def _number_cell(raw: object, what: str) -> float | None:
    """A numeric cell as a float, or `None` for absent — refusing as this module's own error.

    Every conversion in the parser goes through here so a future upstream release that writes `"n/a"`
    into a band bound surfaces as a `StrchiveError` the CLI can diagnose, rather than as a bare
    `ValueError` traceback past both command handlers. A JSON boolean is refused rather than coerced:
    `float(True)` is `1.0`, which would read as a real bound.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise StrchiveError(f"{what} is a boolean: {raw!r}")
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise StrchiveError(f"{what} is not a number: {raw!r}") from exc


def _count_cell(raw: object, what: str) -> int | None:
    """A motif repeat count as an int, or `None` where the structure leaves it open (HTT's `CAG` does)."""
    value = _number_cell(raw, what)
    if value is None:
        return None
    if not float(value).is_integer():
        raise StrchiveError(f"{what} is not a whole number of copies: {raw!r}")
    return int(value)


def _strings(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if item)
    raise StrchiveError(f"expected a string or a list of strings, got {type(raw).__name__}")


def parse_locus(record: dict) -> StrchiveLocus:
    """One catalogue record → the reduced locus, or a refusal naming what was wrong with it."""
    gene = (record.get("gene") or "").strip()
    locus_id = (record.get("id") or "").strip()
    if not gene or not locus_id:
        raise StrchiveError(f"a catalogue record carries no id/gene: {record.get('id')!r}")
    bands: list[Band] = []
    for name in BAND_NAMES:
        lo = _number_cell(record.get(f"{name}_min"), f"{locus_id} {name}_min")
        hi = _number_cell(record.get(f"{name}_max"), f"{locus_id} {name}_max")
        # A band with neither bound is absent, not an open interval covering the axis. Twelve of the
        # published loci state no bands at all, and reading those as "benign everywhere" would have
        # the check report a disagreement against a claim the source never made.
        if lo is None and hi is None:
            continue
        bands.append(Band(name, lo, hi))
    structure = tuple(
        (
            str(item.get("motif") or ""),
            _count_cell(item.get("count"), f"{locus_id} locus_structure count"),
            str(item.get("type") or ""),
        )
        for item in (record.get("locus_structure") or [])
        if isinstance(item, dict)
    )
    ref_copies = _number_cell(record.get("ref_copies"), f"{locus_id} ref_copies")
    return StrchiveLocus(
        locus_id=locus_id,
        gene=gene,
        reference_motifs=_strings(record.get("pathogenic_motif_reference_orientation")),
        gene_motifs=_strings(record.get("pathogenic_motif_gene_orientation")),
        bands=tuple(bands),
        mondo=_strings(record.get("mondo")),
        ref_copies=ref_copies,
        locus_structure=structure,
        disease=(record.get("disease") or None),
    )


def load_strchive_catalogue(path: Path) -> StrchiveCatalogue:
    """Read a built snapshot directory, or a bare `STRchive-loci.json`.

    Both are accepted for the reason `acmg` accepts both a built snapshot and an explicit list: a
    snapshot carries `release.json` and therefore a release label the record can name, while an
    operator who has simply downloaded the upstream file should not be told to build one first. What a
    bare file cannot supply is the label, and `dataset` stays `None` there rather than being invented
    from the filename (`@currency-asks-the-source-not-the-cache`).
    """
    path = Path(path)
    release_path: Path | None = None
    if path.is_dir():
        release_path = path / RELEASE_FILENAME
        path = path / STRCHIVE_CATALOGUE_FILENAME
    else:
        sibling = path.parent / RELEASE_FILENAME
        release_path = sibling if sibling.is_file() else None
    if not path.is_file():
        raise StrchiveUnavailable(f"no STRchive catalogue at {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StrchiveError(f"{path} is not readable as JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise StrchiveError(f"{path} is not a list of loci (got {type(payload).__name__})")

    dataset: str | None = None
    source_url: str | None = None
    if release_path is not None and release_path.is_file():
        try:
            release = json.loads(release_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A snapshot whose provenance file is damaged still holds a readable catalogue; losing the
            # label is a weaker outcome than refusing the comparison, and the record says `None`.
            logger.warning("Could not read %s (%s); the release label is unknown.", release_path, exc)
        else:
            dataset = (release.get("dataset") or None) if isinstance(release, dict) else None
            source_url = (release.get("source_url") or None) if isinstance(release, dict) else None
    return StrchiveCatalogue(
        loci=tuple(parse_locus(record) for record in payload if isinstance(record, dict)),
        dataset=dataset,
        source_url=source_url,
        path=path,
    )


# ── The comparison ──────────────────────────────────────────────────────────────────────────────


#: Every way an authored band table and a catalogue's bands can differ, with the sentence each one
#: gets. A verdict function with several arms owes a reason function with the same arms, pairwise
#: distinct (`@answered-is-not-absent`) — so the kinds and their sentences are one map rather than a
#: chain of `if`s, and a test asserts the two sets are equal.
#:
#: `ceiling_only_in_source` is its own kind rather than a `ceiling_disagreement` against an open bound,
#: because it is the one finding whose *remedy is to do nothing*: it is what `pathogenic_max` looks
#: like from here, and the item's whole point is that it must never be written.
_FINDING_SENTENCES: dict[str, str] = {
    "boundary_only_in_module": (
        "the module divides the axis at {value}, inside {other}, where {source} states no boundary"
    ),
    "boundary_only_in_source": (
        "{source} divides the axis at {value}, inside {other}, where the module states no boundary"
    ),
    "floor_only_in_module": (
        "the module's lowest bound is {value}, inside {other}, so {source} classifies counts below it "
        "that no bin in this module answers for"
    ),
    "ceiling_disagreement": (
        "the highest bound is {value} in the module and {source_value} in {source}"
    ),
    "ceiling_only_in_source": (
        "{source} closes the axis at {source_value} where the module's top bin is open above; this is "
        "a corpus maximum, not a clinical bound, and it is reported rather than written — a longer "
        "allele would otherwise match no bin at all"
    ),
    "ceiling_only_in_module": (
        "the module closes the axis at {value}, where {source}'s highest band is open above"
    ),
}


@dataclass(frozen=True)
class BandFinding:
    """One difference between an authored bin group and the catalogue locus it was compared against."""

    kind: str
    group_key: tuple
    locus_id: str
    value: float | None = None
    source_value: float | None = None
    other: Band | None = None

    def __str__(self) -> str:
        sentence = _FINDING_SENTENCES[self.kind].format(
            value="open" if self.value is None else _number(self.value),
            source_value="open" if self.source_value is None else _number(self.source_value),
            other=str(self.other) if self.other is not None else "the axis",
            source=SOURCE_NAME,
        )
        return f"{format_group_key(self.group_key)}: {sentence} (STRchive {self.locus_id})"


@dataclass
class RepeatBandResult:
    """What the comparison put, what it withheld, and why — the tri-state made reportable."""

    findings: list[BandFinding] = field(default_factory=list)
    #: Group keys actually compared against a locus. The attestation's denominator.
    compared: list[tuple] = field(default_factory=list)
    #: `(group key, sentence)` for a group nothing could be compared against. Two different sentences,
    #: because "the catalogue has never heard of this gene" and "it has the gene under another motif"
    #: send a reader to different places.
    withheld: list[tuple[tuple, str]] = field(default_factory=list)
    #: `(gene, motif)` keys several catalogue loci claim. Reported, never resolved by picking one.
    contested: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    dataset: str | None = None
    #: `group key -> the effective tiling the endpoints were compared under`, so a reader can tell
    #: which reading of a shared endpoint the comparison used (`@dense-bin-boundary`).
    tilings: dict[tuple, str | None] = field(default_factory=dict)

    @property
    def groups_in_disagreement(self) -> set[tuple]:
        """Groups carrying at least one finding — the numerator, which must not exceed `compared`."""
        return {finding.group_key for finding in self.findings}


def _intervals(bins: Sequence[MeasureBinRow]) -> list[Band]:
    """Authored bins as intervals, ordered along the axis, open-below first."""
    ordered = sorted(
        bins, key=lambda r: (r.measure_min is not None, r.measure_min if r.measure_min is not None else 0.0)
    )
    return [
        Band(row.phenotype or "bin", row.measure_min, row.measure_max) for row in ordered
    ]


def _floor(intervals: Sequence[Band]) -> float | None:
    """The lowest bound the set states, or `None` when any interval is open below."""
    if not intervals or any(iv.lo is None for iv in intervals):
        return None
    return min(iv.lo for iv in intervals if iv.lo is not None)


def _ceiling(intervals: Sequence[Band]) -> float | None:
    """The highest bound the set states, or `None` when any interval is open above."""
    if not intervals or any(iv.hi is None for iv in intervals):
        return None
    return max(iv.hi for iv in intervals if iv.hi is not None)


def _cuts(intervals: Sequence[Band]) -> list[float]:
    """Where a set of intervals divides the axis: every lower bound above the floor, sorted.

    **Lower bounds only, and that is what makes the comparison tiling-independent.** Under quantised
    tiling adjacent bins are `[6,26] [27,35]` and under continuous they are `[6,26] [26,35]`, so the
    *upper* bound of a bin means different things on the two readings while the lower bound of the
    next one is the division either way (`@dense-bin-boundary`). An open-below interval leaves the
    floor undefined, and then every finite lower bound is a division.
    """
    floor = _floor(intervals)
    return sorted(
        {iv.lo for iv in intervals if iv.lo is not None and (floor is None or iv.lo > floor)}
    )


def _source_cut_windows(bands: Sequence[Band]) -> list[tuple[float, float, Band, Band]]:
    """Where the catalogue divides the axis, as the closed window an authored cut may land in.

    A window rather than a point, because the two tilings spell one division differently and the
    source states its bands in the quantised form: `benign 6–26` beside `intermediate 27–35` is the
    same division a continuous table writes as a shared `26`. The window `[26, 27]` admits both, and
    `resolve_tiling` decides only which endpoint the *message* names — the verdict is the same under
    either reading, which is why this is one rule rather than a branch.

    A gap wider than one step widens the window rather than inventing a boundary inside it: with the
    source silent between two bands, any authored cut in there is a division the source neither
    states nor contradicts.
    """
    windows: list[tuple[float, float, Band, Band]] = []
    for lower, upper in zip(bands, bands[1:], strict=False):
        if lower.hi is None or upper.lo is None:
            continue
        lo, hi = sorted((lower.hi, upper.lo))
        windows.append((lo, hi, lower, upper))
    return windows


def compare_bands(
    group_key: tuple, bins: Sequence[MeasureBinRow], locus: StrchiveLocus, *, tiling: str | None
) -> list[BandFinding]:
    """One authored bin group against one catalogue locus. Reports; repairs nothing.

    Three questions, kept apart because they have three different remedies: where the two divide the
    axis, where the axis starts, and where it ends. The last is the one `pathogenic_max` lands in, and
    it gets its own finding kind so that "the source states a ceiling the module does not" can never
    be mistaken for "the two ceilings disagree".
    """
    authored = _intervals(bins)
    source = list(locus.bands)
    findings: list[BandFinding] = []

    windows = _source_cut_windows(source)
    authored_cuts = _cuts(authored)
    for cut in authored_cuts:
        if any(lo <= cut <= hi for lo, hi, _, _ in windows):
            continue
        inside = next((band for band in source if band.divides(cut)), None)
        if inside is None:
            # Outside every band the source states — it has nothing to say here, so neither has this.
            continue
        findings.append(
            BandFinding("boundary_only_in_module", group_key, locus.locus_id, value=cut, other=inside)
        )

    for lo, hi, _lower, upper in windows:
        if any(lo <= cut <= hi for cut in authored_cuts):
            continue
        stated = hi if tiling == "quantised" or tiling is None else lo
        inside = next((iv for iv in authored if iv.divides(stated, tiling=tiling)), None)
        if inside is None:
            continue
        findings.append(
            BandFinding(
                "boundary_only_in_source",
                group_key,
                locus.locus_id,
                value=stated,
                other=inside,
                source_value=upper.lo,
            )
        )

    # **The floor is gated the same way the boundaries are, and that is what keeps it quiet.** An
    # unconditional "the two lowest bounds differ" fires on a module that simply does not bin the low
    # end — binning only the clinically actionable range is a normal, deliberate shape, and calling it
    # a disagreement about a threshold puts a false finding into a hashed record. The question that
    # *is* worth asking is whether the module's floor cuts a band the source classifies, so that a
    # count the catalogue calls benign matches no bin at all. A module binning *wider* than the
    # catalogue withholds: the source has nothing to say down there, and unknown never negates.
    module_floor = _floor(authored)
    if module_floor is not None:
        cut = next((band for band in source if band.divides(module_floor)), None)
        if cut is not None:
            findings.append(
                BandFinding(
                    "floor_only_in_module", group_key, locus.locus_id,
                    value=module_floor, other=cut, source_value=_floor(source),
                )
            )

    module_ceiling, source_ceiling = _ceiling(authored), _ceiling(source)
    if module_ceiling is None and source_ceiling is not None:
        findings.append(
            BandFinding(
                "ceiling_only_in_source", group_key, locus.locus_id, source_value=source_ceiling
            )
        )
    elif module_ceiling is not None and source_ceiling is None and source:
        findings.append(
            BandFinding("ceiling_only_in_module", group_key, locus.locus_id, value=module_ceiling)
        )
    elif (
        module_ceiling is not None
        and source_ceiling is not None
        and module_ceiling != source_ceiling
    ):
        findings.append(
            BandFinding(
                "ceiling_disagreement", group_key, locus.locus_id,
                value=module_ceiling, source_value=source_ceiling,
            )
        )
    return findings


def load_repeat_alleles(spec_dir: Path) -> list[RepeatAlleleRow]:
    """The module's authored band table, or `[]` when it carries none."""
    path = Path(spec_dir) / REPEAT_ALLELES_CSV
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, RepeatAlleleRow, REPEAT_ALLELES_CSV)
    if errors:
        # Structural, so it refuses in **both** modes: `strict` not escalating a source disagreement
        # says nothing about a file that will not load.
        raise StrchiveError(f"{REPEAT_ALLELES_CSV} is invalid: {errors[0]}")
    return rows


def check_repeat_bands(
    spec_dir: Path,
    *,
    catalogue: Path | StrchiveCatalogue | None = None,
    mode: str = "best_effort",
    write: bool = True,
) -> RepeatBandResult:
    """Compare a module's `repeat_alleles.csv` bands against STRchive's. Reports, never repairs.

    `mode` is carried for the report and **is not a severity ladder here**: a catalogue drawing a
    threshold in a different place from an expert author is a difference between authorities, and
    `strict` refusing it would have the format pick the winner. The one thing `strict` still refuses
    is structural — an unreadable table — and that refuses in `best_effort` too.
    """
    spec_dir = Path(spec_dir)
    result = RepeatBandResult(mode=mode)

    # A provisioned catalogue is used without being named — see `resolve_strchive_reference`. Resolved
    # here rather than at the `catalogue is None` branch below so that a built snapshot is found
    # before the *no reference* message is composed, and only after the table has been read: a module
    # with no band table asks nothing, and looking for a catalogue to answer it would be work done for
    # a question nobody put.
    rows = load_repeat_alleles(spec_dir)
    if not rows:
        # The check does not *apply*: a module with no band table has posed no question a repeat
        # catalogue could answer, and attesting would mine a nonce and publish a
        # `manifest.verification` block about it (`pgx.enrich_pgx`'s rule, same reasoning).
        return result

    groups = _bin_groups(rows)
    if not groups:
        note = (
            f"{REPEAT_ALLELES_CSV} carries only unresolved sentinel rows, so it states no band for "
            f"a catalogue to disagree with"
        )
        result.warnings.append(note)
        return _attest(
            result, spec_dir, write=write,
            record=skipped("repeat_band_agreement", "nothing_to_check", detail=note, source=SOURCE_NAME),
        )

    if catalogue is None:
        catalogue = resolve_strchive_reference()
    if catalogue is None:
        note = (
            "repeat-band cross-check skipped: no STRchive catalogue was provisioned. Build one with "
            "`just-dna-enricher strchive build`, or pass a downloaded STRchive-loci.json."
        )
        result.warnings.append(note)
        logger.warning("%s", note)
        return _attest(
            result, spec_dir, write=write,
            record=skipped("repeat_band_agreement", "no_reference", detail=note, source=SOURCE_NAME),
        )

    loaded = (
        catalogue if isinstance(catalogue, StrchiveCatalogue) else load_strchive_catalogue(catalogue)
    )
    result.dataset = loaded.dataset
    index = loaded.by_gene_and_motif()
    known_genes = loaded.genes()

    for group_key, bins in groups.items():
        gene = getattr(bins[0], "gene", None) or ""
        motif = getattr(bins[0], "repeat_unit", None) or ""
        candidates = index.get((gene, motif), [])
        if not candidates:
            # Two different absences, two different sentences — a reader chasing "why was my locus not
            # checked" needs to know whether to look at the gene or at the motif's orientation.
            reason = (
                f"{format_group_key(group_key)}: {SOURCE_NAME} lists {gene} but under no motif "
                f"matching {motif!r}, so the two may not be the same locus"
                if gene in known_genes
                else f"{format_group_key(group_key)}: {SOURCE_NAME} carries no locus for {gene}"
            )
            result.withheld.append((group_key, reason))
            continue
        if len(candidates) > 1:
            result.contested.append((gene, motif))
            reason = (
                f"{format_group_key(group_key)}: {SOURCE_NAME} carries "
                f"{len(candidates)} loci keyed ({gene}, {motif}) — "
                f"{', '.join(sorted(locus.locus_id for locus in candidates))} — so which bands to "
                f"compare against is the source's own ambiguity, not this module's"
            )
            result.withheld.append((group_key, reason))
            continue
        locus = candidates[0]
        if not locus.bands:
            reason = (
                f"{format_group_key(group_key)}: {SOURCE_NAME}'s {locus.locus_id} states no bands"
            )
            result.withheld.append((group_key, reason))
            continue
        tiling = resolve_tiling(bins).value
        result.tilings[group_key] = tiling
        result.compared.append(group_key)
        result.findings.extend(compare_bands(group_key, bins, locus, tiling=tiling))

    for finding in result.findings:
        logger.warning("Repeat-band difference — %s", finding)
    for _key, reason in result.withheld:
        logger.info("Repeat bands not compared — %s", reason)

    return _attest(result, spec_dir, write=write, record=verification_record(result))


def verification_record(result: RepeatBandResult) -> VerificationRecord:
    """The `repeat_band_agreement` record: what was compared, or why nothing was.

    `subjects` is **bin groups compared**, and `findings` is **groups in disagreement** — not the
    number of differences. A group can differ in three ways at once (HTT differs on a boundary and on
    a ceiling), and `VerificationRecord` refuses more findings than subjects for exactly the reason
    that would break: a count of sentences is not a count of things checked. The sentences travel in
    `detail`, aggregated, and every one of them is in the log.
    """
    if not result.compared:
        # **`ran` with `subjects=0`, not a skip**, and the encoding is the model's own: 0 subjects with
        # no `skipped` means *ran and had nothing in scope*, which is not the same as *did not run*.
        # The check did run here — a catalogue was read and every authored group was put to it — and
        # `nothing_to_check` is defined as "the module carries no row this check applies to", which is
        # false about a module carrying a band table. The genuinely-inapplicable cases (no table at
        # all, or only `unresolved` sentinels) are skipped earlier, where that member is true.
        return ran(
            "repeat_band_agreement",
            subjects=0,
            findings=0,
            source=SOURCE_NAME,
            release=result.dataset,
            detail=(
                " ".join(reason for _key, reason in result.withheld)
                or "no authored bin group could be matched to a catalogue locus"
            ),
        )
    detail = (
        f"compared {len(result.compared)} repeat-count bin group(s) against {SOURCE_NAME}"
        f"{f' ({result.dataset})' if result.dataset else ''}"
    )
    if result.findings:
        detail += ". " + examples([str(finding) for finding in result.findings])
    if result.withheld:
        # The groups that were NOT compared, in the record and not only in the log: a coverage figure
        # whose denominator lives in stderr is the defect this tier keeps closing.
        detail += f". {len(result.withheld)} group(s) withheld — " + examples(
            [reason for _key, reason in result.withheld]
        )
    return ran(
        "repeat_band_agreement",
        subjects=len(result.compared),
        findings=len(result.groups_in_disagreement),
        source=SOURCE_NAME,
        release=result.dataset,
        detail=detail,
    )


def _attest(
    result: RepeatBandResult, spec_dir: Path, *, write: bool, record: VerificationRecord
) -> RepeatBandResult:
    """Record what this check put into `verification.json`, on every path that put one."""
    if write:
        record_verification([record], spec_dir, error=StrchiveError)
    return result
