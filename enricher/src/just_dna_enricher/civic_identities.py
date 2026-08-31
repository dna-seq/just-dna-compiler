"""Identities CIViC states in a variant's **name** and never puts in its identifier columns.

**Why this table exists at all.** `civic build` places a row from what the source publishes — an
rs-number, or a GRCh38 RefSeq accession it can parse. 53 variants in the `01-Aug-2026` release carry
neither and are dropped as `unresolvable_identity`, and for most of them the identity was published
the whole time, in the variant's own `name`: `N150fs (c.448delA)`, `IVS2+1G>A`, `D1709N`. A `c.` or
protein fragment plus the gene's numbering frame is an allele, and an allele registry will hold it.

**Why the answers are a shipped constant rather than a lookup.** Resolving a name needs the network —
the ClinGen Allele Registry, NCBI, Ensembl — and `civic build` must stay byte-reproducible from a
pinned dated release, which is why the CAID pass runs at *draft* time and never in a build. But these
identities are not a lookup's output: **four of them required a judgement no lookup makes.** A legacy
`IVS2` name that converts structurally to the wrong exon; a name pairing a missense protein label with
a synonymous cDNA change; a protein consequence standing over an intronic allele; an rs-number that is
position-level where two alleles spell the same substitution. Each was adjudicated by hand, against
evidence recorded per variant, and re-deriving that at build time would either be impossible or would
silently pick a side. So the *answer* is data, the *procedure* is written down separately, and the
build stays offline.

The procedure is `docs/probes/CIVIC_IDENTITY_PROTOCOL.md`; the per-variant evidence and the classes
that did **not** resolve are `docs/probes/CIVIC_UNRESOLVED.md`.

**What is deliberately not here.**

- **CIViC 4968 `TP53 R72P`.** It resolves — rs1042522, CA178298 — but its identity is the *reference*
  allele (`NC_000017.11:g.7676154G=`, `c.215C=`): codon 72 is `CCC` = Pro on GRCh38, so CIViC's name
  has reference and alternate inverted. A snapshot row is `chrom/start/ref/alt`, and `ref == alt` is
  not a variant row — the compiler drops such rows by design. The identity exists and this format
  cannot carry it, which is a property of the representation rather than of the record.
- **The two conjunction-named records** (3298, 4210). Each names two alterations; all four alleles are
  identified, and minting one identity for a record naming two would assert a locus the source did
  not. A conjunction is a haplotype plus a diplotype, not a variant row.
- **The 9 liftover-only, the 6 that name a class of event, and the 2 with two readings and nothing to
  choose between them.** No identity to carry, or no way to pick one.

**The name is the key, and that is the safety property.** Every identity below was derived from the
`name` string quoted beside it. A build applies a row only when the release's name matches that string
exactly, so a curated answer can never outlive the record it was an answer *to*: if CIViC re-names a
variant, its row goes `stale` and is counted rather than applied. And a row whose identifier columns
CIViC has since filled goes `superseded` — the source always wins over this table, which also makes a
supersession the cheapest currency signal there is.
"""

from dataclasses import dataclass

#: Emitted as `identity_derivation` for a row placed from this table, so a consumer can exclude the
#: curated class without re-deriving why it exists. Deliberately distinct from `rsid`/`grch38_hgvs`/
#: `both`, which mean "the source published this": these rows are the source's *name*, read.
CURATED_DERIVATION = "curated_name"


@dataclass(frozen=True, slots=True)
class CivicNameIdentity:
    """One curated identity, keyed to the CIViC variant id **and** the name it was derived from."""

    #: CIViC's variant id in the release this was derived against.
    variant_id: int
    #: Gene symbol, carried so a reader can see the row without opening the release.
    gene: str
    #: The exact `variant` cell the identity was read from. A build applies this row only on an exact
    #: match — see the module docstring.
    name: str
    #: GRCh38, VCF convention: 1-based `start`, left-anchored `ref`/`alt` for an indel.
    chrom: str
    start: int
    ref: str
    alt: str
    #: The rs-number where one exists. Absent on 11 of these — the identity exists, the fame does not.
    rsid: str | None = None
    #: The ClinGen allele id the resolution went through, as provenance. **Not** written to the
    #: snapshot's `allele_registry_id`, which is CIViC's own verbatim cell and is empty for every one
    #: of these rows; conflating the two would publish a probe's finding as the source's statement.
    caid: str | None = None
    #: Why this one needed more than a lookup, where it did. Empty for the rows a constructed HGVS
    #: expression answered outright.
    note: str | None = None


#: The curated identities, ordered by `variant_id`. Derived 2026-09-01 against the `01-Aug-2026`
#: release; 33 rows, of the 34 variants that resolved (4968 is excluded above, with its reason).
CIVIC_NAME_IDENTITIES: tuple[CivicNameIdentity, ...] = (
    CivicNameIdentity(
        variant_id=788, gene='CHEK2', name='IVS2+1G>A',
        chrom='22', start=28725242, ref='C', alt='T',
        rsid='rs121908698', caid='CA288309',
        note=(
            "legacy IVS name: the structural conversion gives c.319+1 and is wrong; CHEK2's legacy exon numbering starts at the first coding exon, so the allele is c.444+1G>A. Settled by ClinVar VCV000128075's OtherName list, which carries both spellings."
        ),
    ),
    CivicNameIdentity(
        variant_id=804, gene='RUNX1', name='R135FSX177',
        chrom='21', start=34880553, ref='GT', alt='G',
        rsid='rs587776810', caid='CA248618',
        note=(
            "CIViC names a protein consequence; the allele is an intronic splice-donor deletion (ClinVar VCV000014466, 'intron variant', no protein change). Padded VCF form read from the GRCh38 reference at 21:34880553."
        ),
    ),
    CivicNameIdentity(
        variant_id=1768, gene='VHL', name='L129Q (c.386insAGA)',
        chrom='3', start=10146558, ref='C', alt='CAGA',
        rsid=None, caid='CA2586965635',
    ),
    CivicNameIdentity(
        variant_id=1770, gene='VHL', name='N150fs (c.449del)',
        chrom='3', start=10146621, ref='AA', alt='A',
        rsid='rs794727253', caid='CA020360',
        note=(
            'CIViC publishes NC_000003.12:g.10146622del, which parse_grch38_substitution reads substitutions only. Same allele as variant 3743.'
        ),
    ),
    CivicNameIdentity(
        variant_id=1779, gene='VHL', name='R167fs (c.502insTTGTCCGT)',
        chrom='3', start=10149824, ref='G', alt='GTTGTCCGT',
        rsid='rs398123483', caid='CA020458',
    ),
    CivicNameIdentity(
        variant_id=1844, gene='VHL', name='D143fs (c.430delG)',
        chrom='3', start=10146603, ref='GG', alt='G',
        rsid='rs869025651', caid='CA357015',
    ),
    CivicNameIdentity(
        variant_id=1893, gene='VHL', name='F91* (c.272_273delinsAA)',
        chrom='3', start=10142119, ref='TC', alt='AA',
        rsid=None, caid='CA2499307077',
    ),
    CivicNameIdentity(
        variant_id=1948, gene='VHL', name='R69fs (c.204insG)',
        chrom='3', start=10142051, ref='G', alt='GG',
        rsid='rs2470158072', caid='CA913189244',
    ),
    CivicNameIdentity(
        variant_id=1949, gene='VHL', name='G144fs (c.432insG)',
        chrom='3', start=10146604, ref='G', alt='GG',
        rsid=None, caid='CA2573106040',
    ),
    CivicNameIdentity(
        variant_id=1960, gene='VHL', name='L140fs (c.417_418delTC)',
        chrom='3', start=10146591, ref='CTC', alt='C',
        rsid='rs869025649', caid='CA357039',
    ),
    CivicNameIdentity(
        variant_id=2014, gene='VHL', name='P61fs (c.183insC)',
        chrom='3', start=10142030, ref='C', alt='CC',
        rsid=None, caid='CA2586965632',
    ),
    CivicNameIdentity(
        variant_id=2023, gene='VHL', name='N150fs (c.449_462del)',
        chrom='3', start=10146621, ref='AATATCACACTGCCA', alt='A',
        rsid=None, caid='CA658820719',
    ),
    CivicNameIdentity(
        variant_id=2046, gene='VHL', name='V155L (c.463G>C)',
        chrom='3', start=10146636, ref='G', alt='C',
        rsid='rs869025659', caid='CA351754415',
    ),
    CivicNameIdentity(
        variant_id=2051, gene='DICER1', name='D1709N',
        chrom='14', start=95094127, ref='C', alt='T',
        rsid='rs1595331264', caid='CA390865395',
    ),
    CivicNameIdentity(
        variant_id=2091, gene='VHL', name='T152fs (c.455insA)',
        chrom='3', start=10146627, ref='A', alt='AA',
        rsid=None, caid='CA2586965646',
    ),
    CivicNameIdentity(
        variant_id=2136, gene='VHL', name='H125fs (c.374insA)',
        chrom='3', start=10146547, ref='A', alt='AA',
        rsid=None, caid='CA2499307153',
    ),
    CivicNameIdentity(
        variant_id=2195, gene='DICER1', name='D1709G',
        chrom='14', start=95094126, ref='T', alt='C',
        rsid='rs1555366979', caid='CA390865393',
    ),
    CivicNameIdentity(
        variant_id=2196, gene='DICER1', name='D1709E',
        chrom='14', start=95094125, ref='A', alt='T',
        rsid='rs1890098663', caid='CA390865390',
        note=(
            "rs1890098663 is position-level: 14:95094125 carries A>T and A>C, both p.Asp1709Glu. Chosen by ClinVar's citation attribution for the row's own PMID 22187960; a single line of evidence."
        ),
    ),
    CivicNameIdentity(
        variant_id=2447, gene='VHL', name='V66Gfs*89 (c.197_209del)',
        chrom='3', start=10142043, ref='GTGAACTCGCGCGA', alt='G',
        rsid=None, caid='CA2497028944',
    ),
    CivicNameIdentity(
        variant_id=2455, gene='VHL', name='G114Vfs*45 (c.339delA)',
        chrom='3', start=10142185, ref='GA', alt='G',
        rsid=None, caid='CA645509026',
    ),
    CivicNameIdentity(
        variant_id=2459, gene='VHL', name='L178P (c.532C>T)',
        chrom='3', start=10149856, ref='T', alt='C',
        rsid='rs5030822', caid='CA351756245',
        note=(
            "CIViC's name pairs a missense protein label with a synonymous cDNA change. c.533T>C is the missense allele; c.532C>T is synonymous. CIViC publishes the same allele correctly as its own variant 1748."
        ),
    ),
    CivicNameIdentity(
        variant_id=2638, gene='CBL', name='Y371H',
        chrom='11', start=119278181, ref='T', alt='C',
        rsid='rs267606706', caid='CA123492',
    ),
    CivicNameIdentity(
        variant_id=2851, gene='SMAD4', name='R361C',
        chrom='18', start=51065548, ref='C', alt='T',
        rsid='rs80338963', caid='CA128095',
    ),
    CivicNameIdentity(
        variant_id=2884, gene='CDKN2A', name='c.151-1G>C',
        chrom='9', start=21971209, ref='C', alt='G',
        rsid='rs730881677', caid='CA299032',
    ),
    CivicNameIdentity(
        variant_id=2930, gene='VHL', name='106insR (c.316insGCC)',
        chrom='3', start=10142171, ref='C', alt='CCGC',
        rsid='rs869191373', caid='CA916832608',
    ),
    CivicNameIdentity(
        variant_id=2959, gene='CHEK2', name='R474C c.1420C>T',
        chrom='22', start=28694073, ref='G', alt='A',
        rsid='rs540635787', caid='CA288280',
    ),
    CivicNameIdentity(
        variant_id=3002, gene='NF2', name='c.1396C>T',
        chrom='22', start=29674891, ref='C', alt='T',
        rsid='rs74315504', caid='CA021327',
    ),
    CivicNameIdentity(
        variant_id=3143, gene='VHL', name='F148* (c.443_455delinsA)',
        chrom='3', start=10146616, ref='TTGCCAATATCAC', alt='A',
        rsid=None, caid='CA2573050544',
    ),
    CivicNameIdentity(
        variant_id=3184, gene='VHL', name='V62Cfs*5 (c.180del)',
        chrom='3', start=10142026, ref='GG', alt='G',
        rsid='rs730882037', caid='CA020069',
    ),
    CivicNameIdentity(
        variant_id=3245, gene='VHL', name='C77fs (c.230del)',
        chrom='3', start=10142076, ref='TG', alt='T',
        rsid=None, caid='CA2573106239',
    ),
    CivicNameIdentity(
        variant_id=3741, gene='VHL', name='V87fs (c.255_256insC)',
        chrom='3', start=10142105, ref='C', alt='CC',
        rsid='rs864622545', caid='CA16602181',
    ),
    CivicNameIdentity(
        variant_id=3743, gene='VHL', name='N150fs (c.448delA)',
        chrom='3', start=10146621, ref='AA', alt='A',
        rsid='rs794727253', caid='CA020360',
        note=(
            'Same allele as variant 1770 (CA020360): two CIViC records, one allele.'
        ),
    ),
    CivicNameIdentity(
        variant_id=3744, gene='VHL', name='E55fs (c.163delG)',
        chrom='3', start=10142009, ref='GG', alt='G',
        rsid='rs869025615', caid='CA432536363',
    ),
)

#: Keyed for the build's lookup. Built from the tuple rather than restated, so the two cannot drift.
CIVIC_NAME_IDENTITY_BY_VARIANT: dict[int, CivicNameIdentity] = {
    row.variant_id: row for row in CIVIC_NAME_IDENTITIES
}

#: What became of each curated row in one build. Walked rather than restated: a build asserts that
#: `len(CIVIC_NAME_IDENTITIES)` equals the sum over these, so a state added without a counter cannot
#: hide (`@registry-completeness`).
#:
#: `applied`    — the release still names the variant exactly as this table quotes it, CIViC still
#:                publishes no identifier for it, and the row was placed from here.
#: `superseded` — CIViC now publishes an identity of its own. The source wins; this row stood down.
#:                Also the cheapest currency signal available: it means the upstream has curated.
#: `renamed`    — the variant is there and its `name` has changed. The curated answer was an answer to
#:                a name, and that name is gone, so it is withheld. On a full release this is the
#:                state worth investigating: someone re-curated the record this table read.
#: `absent`     — the variant is not in this file at all. Distinct from `renamed` on the house's own
#:                rule that a question never put is not an answer (`@unreachable-not-absent`): over a
#:                full release it means withdrawn, and over a slice it means nothing whatever.
CIVIC_CURATION_STATES: tuple[str, ...] = ("applied", "superseded", "renamed", "absent")
