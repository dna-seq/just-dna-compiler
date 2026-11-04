"""Two authorities' placements of one rsID, compared before a row is written (RM267).

**The gap this closes.** The resolver chain asks its links in order and keeps the first answer: the
Ensembl snapshot, then the ClinVar snapshot for what Ensembl missed, then live Ensembl and gnomAD. The
same run already holds the ClinVar snapshot (for the `clin_sig` cross-check) and may hold ClinVar-GKM
(RM305), yet nothing compared a placement one link gave against another's. So every coordinate in
`resolution.csv` had one witness, and `authority=ensembl` read the same whether a second authority
agreed, disagreed or was never asked. S117's case is the one that matters: Ensembl's VCF dump anchors
`rs8176719` (ABO O1) at `9:133257520 G>GC`, a different haplotype from ClinVar's `9:133257521 T>TC`
(GRCh38 reads `GGGG T ACC` at 517–524). The wrong anchor base is a real base, so the reference-allele
check passes it, and RM31's tolerance calls the position difference undecided.

**The comparison, per allele, in the order that needs least.** For each allele the first authority
gives, the witness's *counterparts* are its alleles for the same rsID on the same contig, within the
window an indel can slide in, with the same kind of event: an insertion or deletion of the same length,
or a substitution to the same bases. A counterpart is the same event when

1. the spellings are identical (nothing needed);
2. both are substitutions — a substitution has one spelling once its shared flank is trimmed
   (`parsimony_reduce`'s rule), so the trimmed spellings decide it;
3. both mint a VRS id, compared exactly — the id is over the fully justified allele, so it needs no
   tolerance (RM270's probe: a respelling mints one id, `rs8176719`'s pair mints two). We mint both
   sides ourselves: ClinVar-GKM's own ids are VRS 2.1.1 and ours 2.0 (`ClinVarGkmWitness.ids_comparable`),
   so its VCF spelling is minted here rather than its id compared;
4. both left-align against the reference window (`sequences._left_align`), compared as tuples;
5. otherwise the comparison is **undecided** — counted, never read as agreement (`@tautology-zero`).

An allele with no counterpart is **unplaced** by that witness: the witness holds a different allele of
the rsID, or none. That is not a disagreement — ClinVar holds the alleles somebody submitted, not every
allele dbSNP knows — and it is the class whose count is published as "one witness".

**What a disagreement does.** The locus holding the disputed allele is withheld: no row is written for
it, and the finding names both placements. A locus of the same rsID nobody disputes is still written.
When every locus is withheld the caller routes the subject like an unreachable one — an rsID-only
subject stays unresolved, a subject that authored its own coordinate keeps it. Nothing is
rewritten (PROPOSAL_0_8_PT2 §4 question 3: no corrected spelling in 0.8, `@enrichment-is-validation`).

**Independence.** A placement the ClinVar link filled has no independent witness here — ClinVar-GKM is
ClinVar's own release — so it is counted with the one-witness class and never compared.

**Ensembl REST, the third witness, online only.** Neither loaded witness holds S117's own `rs8176719`
(ClinVar has no record there, ClinVar-GKM lacks it), so against them it is one witness. REST does hold it,
as `-/C` at the interbase point RM268 anchors to `9:133257521 T>TC`. So for an indel the Ensembl snapshot
placed and no loaded witness holds, an online run asks the live REST rung (`live_witness_subjects`,
`ask_live_witness`) and compares the answer by the same ladder. REST and the snapshot are one authority,
Ensembl, so the witness is named `ensembl` — the licensed source `placement_witness` joins
`sources.csv` on — and a comparison against it is **self-consistent, not independent** (RM292): it still
catches the snapshot's dump disagreeing with Ensembl's own REST mapping, which is S117's case, but an
agreement proves nothing about the placement, so a REST-only agreement stays in the one-witness count.
A request that got no answer (unreachable after retries, or an anchor base that could not be read) leaves
REST *not asked* for that rsID — counted, never agreement (`@unreachable-not-absent`) — and `--offline`
asks nothing.
"""

import logging
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_overlay
from just_dna_format.alleles import parsimony_reduce
from just_dna_format.vocab import ALLELE_PATTERN

from just_dna_enricher import clinvar
from just_dna_enricher.clinvar_gkm import ClinVarGkmWitness
from just_dna_enricher.sequences import _LEFT_ALIGN_WINDOW, _left_align
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)

#: The two witnesses this tier holds offline, by the names `sources.csv` and the RM292 roster use.
CLINVAR_WITNESS = "clinvar"
CLINVAR_GKM_WITNESS = "clinvar_gkm"
#: The live one: Ensembl REST, named by its licensed source because `placement_witness` joins
#: `sources.csv` (`@source-vs-authority`). It is the snapshot's own authority, so it witnesses the
#: snapshot self-consistently, never independently.
ENSEMBL_WITNESS = "ensembl"
#: The resolution link whose placements the REST witness is asked about: the Ensembl snapshot. A row the
#: live rung itself gave is never re-asked.
_SNAPSHOT_LINK = "cache"

#: The authorities a witness may not speak for, because it is that authority's own data.
_NOT_INDEPENDENT: dict[str, frozenset[str]] = {
    CLINVAR_WITNESS: frozenset({CLINVAR_WITNESS, CLINVAR_GKM_WITNESS}),
    CLINVAR_GKM_WITNESS: frozenset({CLINVAR_WITNESS, CLINVAR_GKM_WITNESS}),
}
#: The authority each witness belongs to. A witness compared against a placement of its own authority
#: (REST against the snapshot) is asked — its disagreement is a finding — but it is never an independent
#: witness, so its agreement leaves the rsID in the one-witness count. One map, so a witness whose name
#: differs from its authority (`clinvar_gkm` is ClinVar's) cannot pass for independent by spelling.
_AUTHORITY_OF_WITNESS: dict[str, str] = {
    CLINVAR_WITNESS: CLINVAR_WITNESS,
    CLINVAR_GKM_WITNESS: CLINVAR_WITNESS,
    ENSEMBL_WITNESS: ENSEMBL_WITNESS,
}

#: The row verdicts (`ResolutionRow.placement_verdict`, `vocab.VALID_PLACEMENT_VERDICTS`).
SAME_EVENT = "same_event"
UNDECIDED = "undecided"
UNPLACED = "unplaced"

Mint = Callable[[str, int, str, str], str | None]
ReadWindow = Callable[[str, int, int], str | None]


@dataclass(frozen=True)
class Allele:
    """One allele of one placement, in VCF spelling."""

    chrom: str
    start: int
    ref: str
    alt: str

    def __str__(self) -> str:
        return f"{self.chrom}:{self.start} {self.ref}>{self.alt}"

    @property
    def spelling(self) -> tuple[str, int, str, str]:
        return (self.chrom, self.start, self.ref, self.alt)


def _trimmed(allele: Allele) -> tuple[int, str, str]:
    """`(start, ref, alt)` with the shared flank trimmed, right then left (`parsimony_reduce`'s rule)."""
    ref, alt, start = allele.ref, allele.alt, allele.start
    while ref and alt and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:
        ref, alt, start = ref[1:], alt[1:], start + 1
    return start, ref, alt


def _kind(allele: Allele) -> tuple[str, int, str]:
    """What left-alignment cannot change: the event's type, its length, and a substitution's bases.

    An indel's payload is left out on purpose — sliding it inside a repeat rotates it (`AG` reads as
    `GA` one base on), so only its length pairs two spellings of one event.
    """
    reduced = parsimony_reduce([allele.ref, allele.alt])
    _, ref, alt = _trimmed(allele)
    if "" in reduced and len(reduced) == 2:
        (payload,) = reduced - {""}
        return ("insertion" if len(allele.alt) > len(allele.ref) else "deletion", len(payload), "")
    return ("substitution", len(alt), alt) if len(ref) == len(alt) else ("complex", len(ref) - len(alt), alt)


def _counterparts(allele: Allele, witness: Sequence[Allele]) -> list[Allele]:
    kind = _kind(allele)
    return [
        w
        for w in witness
        if w.chrom == allele.chrom and abs(w.start - allele.start) <= _LEFT_ALIGN_WINDOW and _kind(w) == kind
    ]


def same_event(first: Allele, second: Allele, *, mint: Mint, read_window: ReadWindow | None) -> bool | None:
    """Whether two spellings are one event — `True`, `False`, or `None` when nothing here can tell.

    The module docstring gives the ladder. `None` is not a weak `False`: it is a respelling this run
    had no sequence to settle, and it is counted apart.
    """
    if first.spelling == second.spelling:
        return True
    kind = _kind(first)
    if kind[0] == "substitution" and kind == _kind(second):
        return _trimmed(first) == _trimmed(second)
    ids = (mint(*first.spelling), mint(*second.spelling))
    if ids[0] is not None and ids[1] is not None:
        return ids[0] == ids[1]
    if read_window is not None:
        left = (
            _left_align(*first.spelling, read_window=read_window),
            _left_align(*second.spelling, read_window=read_window),
        )
        if left[0] is not None and left[1] is not None:
            return left[0] == left[1]
    return None


def alleles_of(loci: Iterable[Mapping[str, object]]) -> list[Allele]:
    """Every nucleotide allele the loci name, one per ALT. A symbolic or empty ALT names no placement."""
    out: list[Allele] = []
    for locus in loci:
        chrom, start, ref = locus.get("chrom"), locus.get("start"), str(locus.get("ref") or "").upper()
        if chrom is None or start is None or not ALLELE_PATTERN.match(ref):
            continue
        for alt in str(locus.get("alts") or "").split(","):
            alt = alt.strip().upper()
            if alt and alt != ref and ALLELE_PATTERN.match(alt):
                out.append(Allele(str(chrom), int(start), ref, alt))  # type: ignore[arg-type]
    return out


def locus_key(locus: Mapping[str, object]) -> tuple[str, int, str, str]:
    """How a row's verdict is found again after the hosting filter: the locus as the link gave it."""
    return (
        str(locus.get("chrom")),
        int(locus.get("start") or 0),
        str(locus.get("ref")),
        str(locus.get("alts")),
    )  # type: ignore[arg-type]


@dataclass(frozen=True)
class PlacementDisagreement:
    """An rsID two authorities place as two different events. Both placements are named."""

    rsid: str
    authority: str
    placed: tuple[str, ...]
    witness: str
    witness_placed: tuple[str, ...]

    def __str__(self) -> str:
        return (
            f"{self.rsid}: {self.authority} places {', '.join(self.placed)}; {self.witness} places "
            f"{', '.join(self.witness_placed)}"
        )


@dataclass
class PlacementCheck:
    """What the comparison did (RM267) — the `PairCheck` shape, so an empty list cannot read as a pass.

    * `witnesses` — the second authorities this run had loaded or asked, sorted; empty means none was.
    * `subjects` — rsIDs compared: at least one allele a witness asked about it also placed. The
      record's denominator.
    * `disagreements` — one per (allele, witness) placed as a different event. Its locus is withheld.
    * `withheld_loci` — `(rsid, locus_key)` of every locus holding a disputed allele; never written.
    * `undecided` — rsIDs with no withheld locus left unsettled: some allele could not be decided.
    * `single_witness` — rsIDs this run placed that no independent witness placed: the ClinVar link's
      own fills, every rsID none of whose alleles a witness holds, and every rsID only its own
      authority's other surface compared (Ensembl REST against the snapshot). Published beside the
      finding (`@tautology-zero`).
    * `self_consistent` — compared rsIDs whose only witness was their own authority (REST for a
      snapshot placement): a disagreement there is a finding, an agreement proves nothing.
    * `not_asked` — rsIDs a live witness was due to be asked about and got no answer for: unknown.
    * `reported_by` — the authorities whose placements were compared, the record's checked side.
    * `placed_by` — the authorities of every placement looked at, which a skip names instead.
    * `placed` — every rsID the comparison looked at, the denominator `single_witness` is a part of.
    * `rows` — `(rsid, locus_key) -> (witness, verdict)` for the row writer.
    * `not_checked` — a `VALID_VERIFICATION_SKIPS` key when the comparison could not run at all.
    """

    witnesses: tuple[str, ...] = ()
    subjects: int = 0
    disagreements: list[PlacementDisagreement] = field(default_factory=list)
    withheld_loci: set[tuple[str, tuple[str, int, str, str]]] = field(default_factory=set)
    undecided: list[str] = field(default_factory=list)
    single_witness: list[str] = field(default_factory=list)
    self_consistent: list[str] = field(default_factory=list)
    not_asked: list[str] = field(default_factory=list)
    reported_by: set[str] = field(default_factory=set)
    placed_by: set[str] = field(default_factory=set)
    placed: int = 0
    rows: dict[tuple[str, tuple[str, int, str, str]], tuple[str, str]] = field(default_factory=dict)
    not_checked: str | None = None
    _loci_of: dict[str, list[tuple[str, int, str, str]]] = field(default_factory=dict, repr=False)

    @property
    def contested(self) -> list[str]:
        """The rsIDs with at least one disputed placement, sorted — the record's findings."""
        return sorted({d.rsid for d in self.disagreements})

    @property
    def withheld(self) -> list[str]:
        """The rsIDs none of whose placements may be written, sorted: every locus held a disputed allele."""
        return [
            rsid
            for rsid in self.contested
            if all((rsid, key) in self.withheld_loci for key in self._loci_of.get(rsid, ()))
        ]

    def keeps(self, rsid: str, locus: Mapping[str, object]) -> bool:
        """Whether a locus the first authority gave may be written (no allele of it is disputed)."""
        return (rsid, locus_key(locus)) not in self.withheld_loci

    def row_columns(self, rsid: str, locus: Mapping[str, object]) -> tuple[str | None, str | None]:
        """`(placement_witness, placement_verdict)` for one locus about to be written."""
        return self.rows.get((rsid, locus_key(locus)), (None, None))

    def sentences(self) -> list[str]:
        """The counts a reader needs beside the finding, one sentence per class, never per row."""
        out: list[str] = []
        if self.single_witness:
            out.append(
                f"{len(self.single_witness)} of {self.placed} placed rsID(s) had one witness only — no "
                f"independent second authority placed them ({examples(self.single_witness)})"
            )
        if self.self_consistent:
            out.append(
                f"{len(self.self_consistent)} of them were compared with Ensembl REST alone "
                f"({examples(self.self_consistent)}) — Ensembl's own other surface, so self-consistent "
                "rather than independent: a disagreement is still a finding, an agreement proves nothing "
                "about the placement"
            )
        if self.not_asked:
            out.append(
                f"{len(self.not_asked)} rsID(s) Ensembl REST could not be asked about "
                f"({examples(self.not_asked)}) — unreachable after retries, or an answer whose anchor base "
                "could not be read — so it is unknown there, never agreement"
            )
        if self.undecided:
            out.append(
                f"{len(self.undecided)} compared rsID(s) are respellings this run had no reference "
                f"sequence to settle ({examples(self.undecided)}), so no verdict was reached"
            )
        return out


def _allele_verdict(answers: Sequence[bool | None]) -> bool | None | str:
    """One allele over every witness: disputed if any said another event, else agreed if any said the
    same, else undecided; `UNPLACED` when no witness held a counterpart at all."""
    if not answers:
        return UNPLACED
    return False if False in answers else True if True in answers else None


def compare_placements(
    placed: Mapping[str, Sequence[Mapping[str, object]]],
    authority_of: Mapping[str, str | None],
    witnesses: Mapping[str, Mapping[str, Sequence[Mapping[str, object]]]],
    *,
    mint: Mint,
    read_window: ReadWindow | None,
    asked_about: Mapping[str, Collection[str]] | None = None,
) -> PlacementCheck:
    """Compare every rsID in `placed` against every loaded witness it is independent of.

    `placed` is `rsid -> loci` as the first authority gave them (before the hosting filter: the
    question is where the source puts the rsID, not which locus the module can use); `authority_of`
    names that authority per rsID; `witnesses` is `witness name -> rsid -> loci`. A witness in
    `asked_about` was asked only about the rsIDs it lists there (the live REST witness); every other
    rsID's row does not name it. A loaded snapshot witness is asked about every rsID.

    **A witness that is the rsID's own authority compares, but witnesses nothing independently**
    (Ensembl REST for a snapshot placement): its disagreement withholds like any other, and its
    agreement leaves the rsID in the one-witness count.

    **Withheld per locus, judged per allele.** A locus holding a disputed allele is not written; a
    locus of the same rsID nobody disputes still is, so one contested allele does not cost the module
    a placement both authorities agree on. A written row reads `same_event` only when every one of
    its ALTs was placed the same by a witness — an ALT no witness holds makes the row `unplaced`, an
    unsettled one `undecided`, so no allele reads as confirmed that was not.
    """
    check = PlacementCheck(witnesses=tuple(sorted(witnesses)), placed=len(placed))
    scope = asked_about or {}
    for rsid in sorted(placed):
        loci = placed[rsid]
        check._loci_of[rsid] = [locus_key(locus) for locus in loci]
        authority = authority_of.get(rsid) or ""
        if authority:
            check.placed_by.add(authority)
        asked = sorted(
            w
            for w in witnesses
            if authority not in _NOT_INDEPENDENT.get(w, frozenset()) and (w not in scope or rsid in scope[w])
        )
        witnessed_by: set[str] = set()
        theirs = {witness: alleles_of(witnesses[witness].get(rsid, ())) for witness in asked}
        per_locus: dict[tuple[str, int, str, str], list[bool | None | str]] = {}
        for locus in loci:
            verdicts: list[bool | None | str] = []
            for allele in alleles_of([locus]):
                answers: list[bool | None] = []
                for witness in asked:
                    counterparts = _counterparts(allele, theirs[witness])
                    if not counterparts:
                        continue
                    witnessed_by.add(witness)
                    said = [same_event(allele, w, mint=mint, read_window=read_window) for w in counterparts]
                    answer = True if True in said else None if None in said else False
                    answers.append(answer)
                    if answer is False:
                        check.disagreements.append(
                            PlacementDisagreement(
                                rsid=rsid,
                                authority=authority,
                                placed=(str(allele),),
                                witness=witness,
                                witness_placed=tuple(str(w) for w in counterparts),
                            )
                        )
                verdicts.append(_allele_verdict(answers))
            per_locus[locus_key(locus)] = verdicts
        if witnessed_by:
            check.subjects += 1
            if authority:
                check.reported_by.add(authority)
        independent = {w for w in witnessed_by if _AUTHORITY_OF_WITNESS.get(w, w) != authority}
        if not independent:
            check.single_witness.append(rsid)
            if witnessed_by:
                check.self_consistent.append(rsid)
        unsettled = False
        for key, verdicts in per_locus.items():
            if False in verdicts:
                check.withheld_loci.add((rsid, key))
                continue
            if not asked:
                continue
            if verdicts and all(v is True for v in verdicts):
                verdict = SAME_EVENT
            elif None in verdicts:
                verdict, unsettled = UNDECIDED, True
            else:
                verdict = UNPLACED
            check.rows[(rsid, key)] = ("+".join(asked), verdict)
        if unsettled:
            check.undecided.append(rsid)
    return check


Loci = dict[str, list[dict[str, object]]]


def load_witnesses(
    clinvar_ref: Path | None, clinvar_gkm_ref: Path | None, rsids: Sequence[str]
) -> dict[str, Loci]:
    """`witness name -> rsid -> loci` from every second authority located for this run, read locally.

    A located snapshot that will not answer is a witness this run does not have, logged and left out —
    the same footing the ClinVar link gives it. It is never an empty answer: an unusable witness that
    read as "holds nothing" would put every rsID in the one-witness count for the wrong reason.
    """
    found: dict[str, Loci] = {}
    if not rsids:
        return found
    if clinvar_ref is not None:
        try:
            loci, _, _ = clinvar.lookup_loci(clinvar_ref, list(rsids), [])
        except Exception as exc:  # a foreign or stale parquet: the ClinVar link's own rule
            logger.warning(
                "ClinVar reference at %s is present but not queryable (%s); placements are not "
                "compared against it this run.",
                clinvar_ref,
                exc,
            )
        else:
            found[CLINVAR_WITNESS] = {rsid: list(rows) for rsid, rows in loci.items()}
    if clinvar_gkm_ref is not None:
        try:
            placements = ClinVarGkmWitness.load(clinvar_gkm_ref).by_rsids(rsids)
        except Exception as exc:  # a foreign, stale or corrupt slice: the same rule as ClinVar's above
            logger.warning(
                "ClinVar-GKM snapshot at %s is not readable (%s); placements are not compared against "
                "it this run.",
                clinvar_gkm_ref,
                exc,
            )
        else:
            found[CLINVAR_GKM_WITNESS] = {
                rsid: [{"chrom": p.chrom, "start": p.pos, "ref": p.ref, "alts": p.alt} for p in rows]
                for rsid, rows in placements.items()
            }
    return found


def live_witness_subjects(
    placed: Mapping[str, Sequence[Mapping[str, object]]],
    link_of: Mapping[str, str | None],
    loaded: Mapping[str, Mapping[str, Sequence[Mapping[str, object]]]],
) -> list[str]:
    """The rsIDs Ensembl REST is asked about, sorted: placed by the Ensembl snapshot, with at least one
    allele that is not a substitution, and held by no loaded witness.

    The snapshot only, because S117's class lives in its dump, and a row the live rung gave is REST's own
    answer. Indels only, because a substitution has one spelling and the snapshot cannot respell it. And
    only where no loaded witness holds the rsID, because there REST would add a self-consistent answer
    beside an independent one at the cost of a request.
    """
    return sorted(
        rsid
        for rsid, loci in placed.items()
        if link_of.get(rsid) == _SNAPSHOT_LINK
        and any(_kind(allele)[0] != "substitution" for allele in alleles_of(loci))
        and not any(witness.get(rsid) for witness in loaded.values())
    )


Resolve = Callable[[str], tuple[Sequence[Mapping[str, object]] | None, str | None]]


def ask_live_witness(resolve: Resolve, rsids: Sequence[str]) -> tuple[Loci, list[str]]:
    """Ask the live REST rung (`EnsemblResolver.resolve_rsid_rest`) about each rsID, one at a time.

    Returns `rsid -> loci` for every rsID it answered (an empty list is an answer: REST has no placeable
    locus), and the rsIDs it did not answer — `None` loci, whether the request failed after its retries
    or every mapping's anchor base was unreadable (RM268). Those are not asked, never asked-and-empty.
    Nothing is journalled: a witness's answer is not a placement this run writes.
    """
    answered: Loci = {}
    not_asked: list[str] = []
    for rsid in rsids:
        loci, _ = resolve(rsid)
        if loci is None:
            not_asked.append(rsid)
        else:
            answered[rsid] = [dict(locus) for locus in loci]
    return answered, not_asked


#: The cells a placement is made of. An overlay answers a disputed placement only when it states all of
#: them for the subject: anything less would clear the refusal over half a coordinate.
PLACEMENT_FIELDS: tuple[str, ...] = ("chrom", "start", "ref", "alts")


def answered_placements(spec_dir: Path) -> set[str]:
    """The `resolution.csv` subjects whose overlay states a whole placement (RM267), read-only.

    **Per field, because it silences** (`@a-set-that-silences-is-narrower-than-one-that-raises`): a
    disputed rsID has no row to `update`, so the author's answer is an `insert`, one overlay row per
    field, and it counts only when `insert` and `update` rows for one `(subject, member)` cover every
    `PLACEMENT_FIELDS` cell. A malformed overlay answers nothing; the compile raises on it.
    """
    overrides, errors, _ = load_overlay(Path(spec_dir))
    if errors:
        return set()
    stated: dict[tuple[str, str], set[str]] = {}
    for row in overrides:
        if row.table == "resolution.csv" and row.operation in {"insert", "update"} and row.field:
            stated.setdefault((row.subject, row.member or ""), set()).add(row.field)
    return {subject for (subject, _), fields in stated.items() if set(PLACEMENT_FIELDS) <= fields}
