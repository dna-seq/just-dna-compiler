"""The dated `accepted_and_submitted` VCF — CIViC's own submitted-inclusive publication (RM169).

**Why this file exists, and why it is not the builder's input.** `civic build` reads the dated bulk
TSV pair, every row of which is `evidence_status = accepted`. CIViC also publishes, in the *same*
dated release directory, `<date>-civic_accepted_and_submitted.vcf` — so the wider basis is pinnable
and byte-reproducible, and no API read is needed to reach it. RM160 was filed on the belief that it
was; that belief was wrong, and this module is what replaced it.

**But the VCF is a strict subset of the TSV, and the subset is not arbitrary.** A VCF record needs a
POS, so a CIViC variant with no GRCh37 coordinate cannot appear in one at all. Measured over
`01-Aug-2026`, the accepted VCF carries 473 germline direction rows on 236 variants where the TSV
carries 533 on 290 — and **52 of the 54 it drops are exactly the `unresolvable_identity` class**, the
records whose identity had to be read out of their names (RM159). Reading the VCF as the row source
would silently discard the hardest-won half of this snapshot.

So the TSV pair stays primary and this file is joined onto it for two things it alone carries:

1. **`evidence_status` per evidence item**, which is what makes an accepted row and a submitted row
   distinguishable once both are in the parquet.
2. **The submitted evidence itself** — 642 further direction rows on 247 variants over `01-Aug-2026`,
   of which **127 variants are new** to the snapshot. The whole build goes 507 rows on 270 variants to
   **1,149 on 397**.

**Nothing is placed from a coordinate this file states.** Its POS is **GRCh37**
(`##reference=…GRCh37-lite.fa.gz`), and lifting it is refused on measurement (RM48, and the class-A
working in `docs/probes/CIVIC_UNRESOLVED.md`). Every row is placed from a published identifier read out
of the `CSQ` block, through the same parsers the TSV path uses.

**The `CSQ` block is one entry per evidence item, not per variant.** A single VCF record carries a
comma-separated list, each entry naming a variant *and* the evidence item asserting something about
it, so the join key is `(variant_id, evidence_id)` and a record with three CSQ entries is three rows.
Its field order is declared in the header rather than assumed — see `parse_csq_format`.
"""

import collections
import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: The file, inside the dated release directory the builder already reads.
CIVIC_VCF_FILE = "civic_accepted_and_submitted.vcf"

#: The statuses this file mixes. `accepted` means an editor signed the item off; `submitted` means a
#: curator entered it and no editor has. Kept as CIViC's own words — this is the source's instrument,
#: and translating it into a house grade would lose the thing that makes it worth carrying.
CIVIC_EVIDENCE_STATUSES: frozenset[str] = frozenset({"accepted", "submitted"})

#: Stamped as `identity_derivation` on a row whose variant the TSV pair does not describe, so the
#: identity was read from this file's `CSQ` block instead. The routes inside are the ordinary ones;
#: the member names the *file*, which is the part a consumer cannot otherwise recover.
VCF_DERIVATION = "vcf_csq"

#: The `CSQ` fields this module reads. Checked against the header's own declared order rather than
#: positional-indexed blind: CIViC generates the file with CIViCpy, and a generator that gains a field
#: would silently shift every index after it.
_REQUIRED_CSQ_FIELDS: tuple[str, ...] = (
    "CIViC Variant ID",
    "CIViC Entity ID",
    "CIViC Entity Type",
    "CIViC Entity Status",
    "CIViC Entity Variant Origin",
    "CIViC Entity Significance",
    "CIViC Entity Direction",
    "CIViC Entity Disease",
    "CIViC Entity Source",
    "CIViC Evidence Level",
    "CIViC Evidence Rating",
    # The variant-level half. Read only for variants `VariantSummaries.tsv` does not describe — see
    # `CivicVcfEntry`'s note on why the TSV stays primary everywhere it can answer.
    "CIViC Variant Name",
    "CIViC Variant Aliases",
    "CIViC HGVS",
    "Allele Registry ID",
    "SYMBOL",
    "CIViC Molecular Profile ID",
)

_CSQ_FORMAT_RE = re.compile(r'ID=CSQ.*?Format:\s*([^"]+)"')


class CivicVcfError(RuntimeError):
    """The VCF cannot be read: absent, headerless, or missing a `CSQ` field this module needs."""


@dataclass(frozen=True, slots=True)
class CivicVcfEntry:
    """One `CSQ` entry — one evidence item's view of one variant.

    **The evidence-level fields are carried here because nothing else can supply them.** Origin,
    significance, direction, disease, level, rating and the citation are facts about the *evidence
    item*, and a submitted item has no row in the evidence TSV — so for those items this file is the
    only source.

    **And so is the variant-level half, for the variants the TSV omits.** `VariantSummaries.tsv` is
    accepted-only as well, so **112 of the 127 variants** the submitted evidence introduces have no row
    there at all: no gene, no aliases, no HGVS, no registry id. The same `CSQ` entry carries all four,
    so they are read from here **only when the TSV cannot answer**, and the resulting rows are stamped
    `vcf_csq` rather than folded into the TSV-derived derivations — a row whose identity came from a
    different file is a different provenance claim, and a consumer must be able to see which
    (`@source-vs-authority`, applied to two files of one release). The other 15 join the TSV normally
    and take an ordinary derivation, which is why the stamp counts rows rather than the whole widening.

    Nothing here is read from the record's POS. The VCF is GRCh37 and lifting it stays refused
    (RM48); all 112 place on a published identifier — **57 by ClinGen CAID, 40 by rs-number, 14 by a
    GRCh38 accession, 1 by both** — through the same parsers the TSV path uses, measured over the
    emitted parquet rather than over the file.

    The vocabulary differs from the TSV's: the VCF is `SCREAMING_CASE` (`RARE_GERMLINE`,
    `PREDISPOSITION`, `SUPPORTS`) where the TSV is title case (`Rare Germline`, `Predisposition`,
    `Supports`). One normalizer, applied at the boundary, and both sides' raw tokens are tested
    (`@one-normalizer-two-spellings`).
    """

    variant_id: int
    evidence_id: int
    status: str
    variant_origin: str
    significance: str
    direction: str
    disease: str
    citation_id: str
    source_type: str
    evidence_level: str
    rating: str
    #: Variant-level, from the same entry. Used only where `VariantSummaries.tsv` has no row.
    variant_name: str
    variant_aliases: str
    civic_hgvs: str
    allele_registry_id: str
    gene: str
    #: CIViC's real profile id for this entry. Used as the join key for a CSQ-sourced variant, so the
    #: id in the parquet is the source's own rather than something this builder invented.
    molecular_profile_id: str


def parse_csq_format(header_line: str) -> list[str]:
    """The `CSQ` sub-field names, in the order the file declares them.

    Read rather than hardcoded. The header carries `Format: A|B|C`, and taking it from there is what
    keeps this parser correct when CIViCpy adds a field — a positional constant would keep parsing and
    return the wrong column, which is the failure mode with no symptom.
    """
    match = _CSQ_FORMAT_RE.search(header_line)
    if match is None:
        raise CivicVcfError(
            "the CSQ INFO header does not declare its field order. This file was not written by the "
            "generator this parser was probed against, and reading it positionally would silently "
            "return the wrong column."
        )
    return [field.strip() for field in match.group(1).split("|")]


def read_vcf_entries(path: Path) -> list[CivicVcfEntry]:
    """Every evidence `CSQ` entry in the file, with the status CIViC assigned it.

    Assertion entries are skipped: `CIViC Entity Type` is `evidence` or `assertion`, and an assertion
    is a different table with a different key. Reading both under one name would let an assertion's
    status stand in for an evidence item's.
    """
    path = Path(path)
    if not path.exists():
        raise CivicVcfError(f"CIViC VCF not found: {path}")

    fields: list[str] | None = None
    entries: list[CivicVcfEntry] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("##"):
                if "ID=CSQ" in line:
                    fields = parse_csq_format(line)
                continue
            if line.startswith("#"):
                continue
            if fields is None:
                raise CivicVcfError(
                    f"{path.name} carries data lines before any CSQ header. Nothing can be parsed "
                    f"from it without the declared field order."
                )
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 8:
                continue
            info = dict(pair.split("=", 1) for pair in columns[7].split(";") if "=" in pair)
            for raw in info.get("CSQ", "").split(","):
                if not raw:
                    continue
                entry = _parse_entry(raw, fields)
                if entry is not None:
                    entries.append(entry)

    if fields is None:
        raise CivicVcfError(f"{path.name} has no CSQ INFO header; it is not a CIViC VCF.")
    return entries


def _parse_entry(raw: str, fields: list[str]) -> CivicVcfEntry | None:
    """One `CSQ` entry, or `None` where it is not an evidence item this module can key.

    A `None` here is never a silent drop of something wanted: it is an assertion entry, or an entry
    whose variant/evidence id is absent, and neither can join to a TSV evidence row.
    """
    parts = raw.split("|")
    cell = dict(zip(fields, parts + [""] * (len(fields) - len(parts)), strict=False))
    missing = [name for name in _REQUIRED_CSQ_FIELDS if name not in cell]
    if missing:
        raise CivicVcfError(
            f"the CSQ block is missing the field(s) {missing}. CIViC changed its VCF layout, and this "
            f"reader must be re-probed against the new one rather than guessing."
        )
    if cell["CIViC Entity Type"] != "evidence":
        return None
    variant_id, evidence_id = cell["CIViC Variant ID"].strip(), cell["CIViC Entity ID"].strip()
    if not (variant_id.isdigit() and evidence_id.isdigit()):
        return None
    citation, source_type = _split_source(cell["CIViC Entity Source"])
    status = cell["CIViC Entity Status"].strip()
    if status not in CIVIC_EVIDENCE_STATUSES:
        # A status outside the pair is not silently normalized: the file's whole value here is that it
        # states one, and inventing a default would publish a guess as the source's own word.
        raise CivicVcfError(
            f"evidence {evidence_id} carries status {status!r}, which is not one of "
            f"{sorted(CIVIC_EVIDENCE_STATUSES)}. The status vocabulary moved and every count keyed on "
            f"it is now wrong (`@lookup-with-a-default-hides-a-new-member`)."
        )
    return CivicVcfEntry(
        variant_id=int(variant_id),
        evidence_id=int(evidence_id),
        status=status,
        variant_origin=_title(cell["CIViC Entity Variant Origin"]),
        significance=_title(cell["CIViC Entity Significance"]),
        direction=_title(cell["CIViC Entity Direction"]),
        disease=cell["CIViC Entity Disease"].strip(),
        citation_id=citation,
        source_type=source_type,
        evidence_level=cell["CIViC Evidence Level"].strip(),
        rating=cell["CIViC Evidence Rating"].strip(),
        variant_name=cell["CIViC Variant Name"].strip(),
        # The VCF joins multi-valued cells with `&` where the TSV uses commas. Normalized at the
        # boundary so the shipped parsers, which split on commas and whitespace, need no second
        # dialect (`@snapshot-pipe-alt` is the same rule for a different separator).
        variant_aliases=cell["CIViC Variant Aliases"].replace("&", ",").strip(),
        civic_hgvs=cell["CIViC HGVS"].replace("&", ",").strip(),
        allele_registry_id=cell["Allele Registry ID"].strip(),
        gene=cell["SYMBOL"].strip(),
        molecular_profile_id=cell["CIViC Molecular Profile ID"].strip(),
    )


#: The VCF spells a vocabulary member `RARE_GERMLINE` where the TSV spells it `Rare Germline`. One
#: normalizer for the pair, at the boundary, so nothing downstream learns that two spellings exist
#: (`@one-normalizer-two-spellings`).
#:
#: **Enumerated, not computed.** A `.title()`-shaped rule gets `RARE_GERMLINE` right and
#: `SENSITIVITYRESPONSE` wrong — the TSV writes that one `Sensitivity/Response`, with a separator the
#: VCF simply drops — and `NA` against `N/A`, and `GAIN_OF_FUNCTION` against `Gain of Function`, whose
#: middle word the TSV leaves lowercase. Three exceptions in twenty members is a map, and a map with a
#: guard beside it (`assert_vocabulary_covers`) is what turns a new upstream member into a raised
#: error rather than a silently mis-spelled row.
CIVIC_VCF_TO_TSV: dict[str, str] = {
    # variant origin
    "SOMATIC": "Somatic",
    "RARE_GERMLINE": "Rare Germline",
    "COMMON_GERMLINE": "Common Germline",
    "UNKNOWN": "Unknown",
    "COMBINED": "Combined",
    "MIXED": "Mixed",
    # direction
    "SUPPORTS": "Supports",
    "DOES_NOT_SUPPORT": "Does Not Support",
    # significance
    "PREDISPOSITION": "Predisposition",
    "PROTECTIVENESS": "Protectiveness",
    "SENSITIVITYRESPONSE": "Sensitivity/Response",
    "REDUCED_SENSITIVITY": "Reduced Sensitivity",
    "ADVERSE_RESPONSE": "Adverse Response",
    "RESISTANCE": "Resistance",
    "BETTER_OUTCOME": "Better Outcome",
    "POOR_OUTCOME": "Poor Outcome",
    "POSITIVE": "Positive",
    "NEGATIVE": "Negative",
    "GAIN_OF_FUNCTION": "Gain of Function",
    "LOSS_OF_FUNCTION": "Loss of Function",
    "UNALTERED_FUNCTION": "Unaltered Function",
    "DOMINANT_NEGATIVE": "Dominant Negative",
    "NEOMORPHIC": "Neomorphic",
    "ONCOGENICITY": "Oncogenicity",
    "UNCERTAIN_SIGNIFICANCE": "Uncertain Significance",
    "PATHOGENIC": "Pathogenic",
    "LIKELY_PATHOGENIC": "Likely Pathogenic",
    # shared
    "NA": "N/A",
}


def _title(token: str) -> str:
    """A VCF vocabulary member in the TSV's spelling, or `""` for an empty cell.

    An empty cell returns empty rather than a member: an absent origin is not `Unknown`, which CIViC
    assigns deliberately when a curator has established that it is unknown.
    """
    raw = (token or "").strip()
    if not raw:
        return ""
    if raw not in CIVIC_VCF_TO_TSV:
        raise CivicVcfError(
            f"the VCF vocabulary member {raw!r} has no TSV spelling in CIVIC_VCF_TO_TSV. CIViC gained "
            f"a member, and guessing its title case would put an unmapped token in a column the "
            f"builder keys on (`@lookup-with-a-default-hides-a-new-member`)."
        )
    return CIVIC_VCF_TO_TSV[raw]


def assert_vocabulary_covers(entries: list[CivicVcfEntry]) -> None:
    """Every vocabulary token in the file has a TSV spelling.

    Redundant with `_title` raising per row, and kept because it states the property as an equality
    over a walked set rather than as a side effect of parsing (`@registry-completeness`): a caller can
    put the question directly, and a test can prove the guard without contriving a bad row.
    """
    # Parsing already normalized every member, so an entry here is proof its token mapped.
    seen = {e.variant_origin for e in entries} | {e.significance for e in entries}
    seen |= {e.direction for e in entries}
    unmapped = seen - set(CIVIC_VCF_TO_TSV.values()) - {""}
    if unmapped:
        raise CivicVcfError(f"unmapped vocabulary members after normalization: {sorted(unmapped)}")


def _split_source(cell: str) -> tuple[str, str]:
    """`"24550739 (PUBMED)"` → `("24550739", "PubMed")`, matching the TSV's two columns.

    The VCF packs the citation and its namespace into one cell where the TSV keeps `citation_id` and
    `source_type` apart. Split rather than stored whole, because `_pmid` reads the namespace to decide
    whether the id is a PMID at all — an ASCO abstract number in the PMID column is the confusion that
    rule exists to prevent (`@pmid-vs-pmcid`).
    """
    raw = (cell or "").strip()
    match = re.match(r"^(\S+)\s*\(([^)]+)\)$", raw)
    if match is None:
        return raw, ""
    citation, namespace = match.groups()
    return citation, "PubMed" if namespace.strip().upper() == "PUBMED" else namespace.strip()


def status_by_evidence(entries: list[CivicVcfEntry]) -> dict[int, str]:
    """`evidence_id` → status.

    One entry per evidence item is the normal case, but a multi-variant profile repeats an item once
    per member variant, so the mapping is many-to-one and must agree with itself. A disagreement is
    raised rather than resolved: it would mean the file states two statuses for one item, and picking
    one would publish a coin-flip as the source's word.
    """
    out: dict[int, str] = {}
    for entry in entries:
        seen = out.setdefault(entry.evidence_id, entry.status)
        if seen != entry.status:
            raise CivicVcfError(
                f"evidence {entry.evidence_id} carries both {seen!r} and {entry.status!r} in one "
                f"file; its curation status is not a single fact and cannot be recorded as one."
            )
    return out


def summarize(entries: list[CivicVcfEntry]) -> dict[str, int]:
    """Evidence items per status, over the whole file — the denominator a count here is against."""
    per_item = status_by_evidence(entries)
    counts = collections.Counter(per_item.values())
    return {status: counts.get(status, 0) for status in sorted(CIVIC_EVIDENCE_STATUSES)}
