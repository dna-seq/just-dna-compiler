"""The source-independent resolution table (0.5).

`resolution.csv` is a persisted table of already-resolved variant facts (rsid ↔ coordinate) that the
compiler consumes *instead of* querying any reference — so the compiler owns no source convention
(Ensembl, DuckDB, provisioning) and stays strictly inject-only (CONSTITUTION Principle 2). The table
is filled *before* compilation by anything: an on-disk cache, a live query, or a human. Filling it is
the job of the separate `just-dna-enricher` network tier; the compiler only reads it.

Three parties share this one definition (why it lives in the schema tier, like `manifest.FileEntry`):
the compiler *consumes* it, the enricher *produces* it, and a verify-only client may *re-check* it. It
is dependency-light — pydantic + the stdlib `vocab` leaf, no polars/duckdb/httpx.

A one-to-many rsid (one authored `variant_key` expanding to several loci) is encoded as several rows
sharing `variant_key` with distinct `locus_index`, so the compiler reproduces the expansion without
any source knowledge. The fact columns feed `integrity.resolution_signature`; the provenance columns
are deliberately excluded from it (a human-filled and an Ensembl-filled table with identical facts
must hash equal — see `RESOLUTION_FACT_FIELDS`).
"""

from typing import ClassVar

from pydantic import ConfigDict, Field, field_validator, model_validator

from just_dna_format.base import Companion, PairedFields, both_or_neither, coordinate_key, since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.spelling import ChromCell
from just_dna_format.vocab import (
    VALID_AUTHORED_EVENT_VERDICTS,
    VALID_PLACEMENT_VERDICTS,
    VALID_RESOLUTION_STATUS,
    VALID_RSID_STATUS,
    check_vocab,
    validate_rsid,
)
from just_dna_format.vrs import normalize_chrom, split_vrs_ids, validate_caid, validate_vrs_id_list

# The fact columns that feed `integrity.resolution_signature` — the reproducibility-relevant facts,
# deliberately EXCLUDING the provenance columns (`source`/`status`/`fetched_at`) so a human-filled and
# an Ensembl-filled table carrying identical facts hash equal. This is the structural reason the table
# is hashed by its facts (a stable, producer-independent identity) rather than by its raw bytes.
#
# The rest of the columns are outside too, each for a reason SCHEMAS.md § resolution.csv states at
# length (named here since RM365, which found them outside with no word about them on this tuple):
# `authority` is out as provenance beside `source`: it names the licensed source the link spoke for
# (RM33), which says who answered, not what; a reversed row keeps it (RM380). `rsid_alternates`, `rsid_current` and `rsid_status` are out because
# they describe dbSNP's time-varying state about the rsID, not the placement, and stay out of the
# artifact on purpose. `vrs_id`, `vrs_spec` and `caid` are out as cross-references to the allele the
# coordinate already names; leaving them out meant adding them in 0.5 moved no signature.
# `placement_witness`/`placement_verdict` (RM267), `left_aligned` (RM270) and `authored_event` (RM375)
# are out as the enricher's verdicts about a placement or a spelling — a check's answer recorded on the
# row, not the fact it was checking.
# `source_release` (RM373) is out as provenance beside the claim
# (`@provenance-beside-a-claim-is-outside-content-identity`): it says which release of the link's source
# answered, so two releases agreeing on a placement hash equal, and a release that moves a fact moves
# the fact columns, which is where the signature already sees it.
RESOLUTION_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "rsid",
    "chrom",
    "start",
    "ref",
    "alts",
    "genome_build",
    "locus_index",
)


def authored_coordinate_key(chrom: str | None, start: int | None, ref: str | None) -> str:
    """The authored coordinate an `authored_event` verdict judged, as one comparable string (RM375).

    Written by the enricher beside the verdict and recomputed by the compiler from the row it would
    apply the verdict to, so the two sides cannot spell it two ways: the contig folded
    (`normalize_chrom`), `ref` uppercased, an absent cell an empty segment (`coordinate_key`).
    """
    return coordinate_key(normalize_chrom(chrom), start, ref.upper() if ref else None)


class ResolutionRow(PairedFields):
    """One resolved (or attempted) locus for an authored variant, keyed by the frozen `variant_key`.

    Standalone (not an `AuthoredModel`/`VariantRow` subclass): a resolution fact is not an annotation
    row and must not inherit VariantRow's annotation validators. It reuses the shared `rsid` grammar so
    an rsid here obeys the same rule everywhere, and closes its namespace with `extra="forbid"` like
    the authored models so a typo'd column in `resolution.csv` is caught, not silently dropped.
    """

    #: What makes two rows the same row — and here that is a *subject* rather than a unique row:
    #: `enrich` builds `existing[variant_key] -> list[ResolutionRow]`, because one rsID legitimately
    #: resolves to several loci (`locus_index` orders them) and a re-run replaces the group as a
    #: whole. Hence `_KEY_RULE = "subject"`: uniqueness is *not* the rule, so a tool that treated
    #: this like an equality key would call a legal one-to-many file a duplicate (S51).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key",)
    _KEY_RULE: ClassVar[str] = "subject"
    #: Columns meaningless without a companion (RM366, `base.Companion`). A witness names who was asked
    #: and a verdict what they answered, so one without the other is half a record (both new in 0.8).
    #:
    #: `vrs_spec` with no `vrs_id` is deliberately **not** a pair. Both columns are 0.5, and clearing an
    #: id while keeping its row is the shape an expansion and the `vrs_version_differs` remedy leave
    #: behind; the compiler already reads it as "nothing to pin" (`compilation.vrs_version` is null).
    _PAIRED_FIELDS: ClassVar[tuple[Companion, ...]] = both_or_neither(
        "placement_witness",
        "placement_verdict",
        "a placement witness and its verdict are written together: who was asked, and what they "
        "answered (RM267)",
    ) + both_or_neither(
        "authored_event",
        "judged_coordinate",
        "a verdict on an authored spelling names the spelling it judged, or nothing can tell it from a "
        "stale one (RM375)",
    )

    model_config = ConfigDict(extra="forbid")

    # ── join key: the frozen authored identity (base.derive_variant_key) ──
    variant_key: str = Field(
        json_schema_extra=since("0.5.0"),
        description="Frozen authored identity this row resolves (rsid, else chrom:start:ref)",
    )

    # ── resolved facts (feed resolution_signature) ──
    rsid: str | None = Field(
        json_schema_extra=since("0.5.0"), default=None, description="Resolved dbSNP identifier"
    )
    chrom: ChromCell = Field(
        json_schema_extra=since("0.5.0"), default=None, description="Chromosome without 'chr' prefix"
    )
    start: int | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        ge=0,
        description="1-based genomic position (VCF POS convention; matches the Ensembl and ClinVar snapshots)",
    )
    ref: str | None = Field(json_schema_extra=since("0.5.0"), default=None, description="Reference allele")
    alts: str | None = Field(
        json_schema_extra=since("0.5.0"), default=None, description="Alt allele(s), comma-separated"
    )
    genome_build: str = Field(
        json_schema_extra=since("0.5.0"),
        default="GRCh38",
        description="Assembly the coordinate is in (the RM15 forward hook; GRCh38 today)",
    )
    locus_index: int = Field(
        json_schema_extra=since("0.5.0"),
        default=0,
        ge=0,
        description="0 for a 1:1 resolution; 0..N-1 for a one-to-many rsid expansion",
    )

    # ── cross-references (0.5; OUT of RESOLUTION_FACT_FIELDS this cycle) ──
    # Three separate identifiers for three separate registries (Principle 5 — one column each, never
    # one overloaded `identifier` field): `rsid` above is dbSNP's, `vrs_id` is GA4GH's content-addressed
    # allele name, `caid` is the ClinGen Allele Registry's. They are kept out of the fact set so adding
    # them moves no existing `resolution_signature` while the columns bed in — the identity they carry
    # reaches the artifact through `variant_key` (which derives from the VA for a resolved
    # substitution), so the fact set does not need them.
    vrs_id: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description=(
            "GA4GH VRS allele id (`ga4gh:VA.…`) — one per ALT, comma-joined and **positionally "
            "aligned with `alts`**, so a single-alt row carries a bare id and a multi-allelic one "
            "names each of its alleles in the same order. An empty member is a hole: that allele's id "
            "could not be minted (an indel in an offline run, an off-assembly contig). Minted locally "
            "by `vrs.derive_vrs_allele_id` for a substitution, by the enricher's normalization path "
            "for an indel, and cross-checked against a source's own id (gnomAD serves one) where "
            "available."
        ),
    )
    vrs_spec: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description=(
            "VRS spec version the row's `vrs_id` was minted under, at the spec's minor ('2.0'). The "
            "id rule can change at a minor (VRS 2.1 re-ids some ambiguous insertions), so this is "
            "what tells an id minted under another rule from a corrupt one: a stated version that "
            "differs from the module's pin (`manifest.compilation.vrs_version`) is reported as "
            "`vrs_version_differs`; a substitution that recomputes differently under another VRS major is counted "
            "there, never as a mismatch. Written only by the run that minted the id; "
            "empty means unstated, never the current version (RM304)."
        ),
    )
    caid: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description="ClinGen Allele Registry canonical allele id (`CA<digits>`)",
    )

    # ── provenance (EXCLUDED from resolution_signature; who/what/when filled this) ──
    source: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description="Which link filled this: cache|ensembl-graphql|ensembl-rest|manual|reversed (open)",
    )
    # **Two vocabularies were living under one name** (P5, across two tables). `source` here answers
    # *which link answered* and `sources.csv`'s `source` answers *which licensed source this is* — and
    # `compiler._source_checks` set-differences the two, so every enriched module warned that
    # `ensembl-rest` has no terms recorded. Neither obvious repair works: a `SourceRow` per link makes
    # `ensembl-rest` and `ensembl-graphql` two "sources" with identical terms, and teaching the compiler
    # a link→source map hands it a source convention, which is exactly what P2's 0.5 tightening took
    # away. The missing thing was a third column recording *both*.
    #
    # `source` deliberately keeps its meaning rather than being repurposed as the authority: every
    # `resolution.csv` already written carries link values there, so re-pointing the name would silently
    # change what existing data says. The map from link to authority lives in the enricher, the only
    # tier permitted to know one.
    authority: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description=(
            "The licensed data source the link speaks for — `ensembl` for `ensembl-rest`/"
            "`ensembl-graphql`/`cache`, `clinvar` for the snapshot, `gnomad` for the last-resort link. "
            "Joins `sources.csv.source`. Empty when there is no external authority to declare "
            "(`authored`, `manual`: the module's own bytes or a human). A `reversed` row keeps the "
            "authority of the row it was reversed from, since its facts are still that source's (RM380)."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Resolution outcome: resolved|not_found|ambiguous",
        json_schema_extra={**vocabulary("resolution_status", VALID_RESOLUTION_STATUS), **since("0.5.0")},
    )
    rsid_alternates: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description=(
            "When a reverse (position→rsid) back-fill hit several candidate rsIDs for the *same exact "
            "allele* (a genuine dbSNP merge), the full sorted candidate list (comma-separated); `rsid` "
            "carries the deterministic pick (lowest id) and `status` is 'ambiguous'. Empty otherwise. "
            "Provenance — EXCLUDED from resolution_signature (0.5, provisional)."
        ),
    )
    rsid_current: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description=(
            "The rsID dbSNP serves today when the authored one has been merged away (e.g. `rs3051860` "
            "for an authored `rs3216883`). **Recorded, never substituted** — `weights.parquet` carries "
            "the rsID as identity, so writing the new label into the artifact would migrate "
            "`variant_key` by network lookup and break the round-trip fixed point (Principle 7)."
        ),
    )
    rsid_status: str | None = Field(
        default=None,
        description=(
            "What dbSNP currently says about `rsid`: live|merged|absent|withdrawn. The automated "
            "check never emits `withdrawn` — a retracted rsID is byte-identical to a never-assigned "
            "one through every live endpoint — so it reports `absent` and names both readings. "
            "`withdrawn` is for a curator who has established the retraction by hand, and it refuses "
            "in BOTH modes where `absent` refuses only under strict, because a retracted variant may "
            "invalidate the annotation rather than merely dating it. "
            "Provenance — EXCLUDED from resolution_signature (time-varying external state)."
        ),
        json_schema_extra={**vocabulary("rsid_status", VALID_RSID_STATUS), **since("0.5.0")},
    )
    # ── the placement's second witness (0.8, RM267; EXCLUDED from resolution_signature) ──
    # Two columns, not one: which authority was asked and what it answered are two axes (P5), and a
    # single `clinvar:same_event` cell would be a field piling them up. Both are provenance beside the
    # placement — who else was asked, and what they said — so neither moves a fact signature.
    placement_witness: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "Which second authority was asked where this row's placement sits: `clinvar`, "
            "`clinvar_gkm`, and, on an online run, `ensembl` (Ensembl REST, asked about an indel the "
            "Ensembl snapshot placed and neither of the others holds), `+`-joined in sorted order. "
            "`ensembl` is the snapshot's own authority, so its answer is self-consistent, never "
            "independent. Empty means nobody was asked (none was loaded, the row's own link is "
            "ClinVar's, or REST could not be reached). A placement a witness contradicts is never "
            "written (RM267)."
        ),
    )
    placement_verdict: str | None = Field(
        default=None,
        description=(
            "What `placement_witness` answered: same_event|undecided|unplaced. `undecided` is a "
            "respelling nothing this run held could settle; `unplaced` means the witness holds no "
            "placement of this allele, so the row has one witness only. Empty when nobody was asked."
        ),
        json_schema_extra={**vocabulary("placement_verdict", VALID_PLACEMENT_VERDICTS), **since("0.8.0")},
    )
    # ── the spelling verdict (0.8, RM270; EXCLUDED from resolution_signature) ──
    # A verdict the enricher stamps, never an authored claim: an author-declared normalization would be
    # a claim no offline tier can check, believed by exactly the consumer it misleads (RM270 candidate 2).
    left_aligned: bool | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "Whether the enricher checked this row's spelling to be the leftmost parsimonious one, ALT "
            "by ALT, against the reference: `true` checked left-aligned, `false` checked and not, empty "
            "unknown (no reference read, a non-nucleotide allele, or a row written before 0.8). A "
            "coordinate the enricher fills from an rsID is written left-aligned; a coordinate a module "
            "authored is recorded as authored and only judged here (RM270). A caller's left-aligned "
            "VCF joins a `false` row's indel only through `vrs_id`."
        ),
    )
    # ── the authored spelling's verdict (0.8, RM375; EXCLUDED from resolution_signature) ──
    # The enricher reads the reference; the compiler cannot (P2), so it trusts this record rather than
    # judging two spellings itself (`@a-recorded-judgement-is-a-fact`).
    authored_event: str | None = Field(
        default=None,
        description=(
            "Whether the coordinate the module authored for this subject spells the same event as this "
            "row's locus, judged by the enricher against the reference: same_event|different_event|"
            "undecided. Written only where the two spellings differ (an indel anchored elsewhere in its "
            "repeat, a coordinate from another release's spelling). The compiler reads `same_event` as "
            "agreement and fills only the cells no spelling changes; `undecided` is no verdict, never "
            "agreement. Empty when the spellings are identical, the subject authored no coordinate, or "
            "the row predates 0.8 (RM375)."
        ),
        json_schema_extra={**vocabulary("authored_event", VALID_AUTHORED_EVENT_VERDICTS), **since("0.8.0")},
    )
    judged_coordinate: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "The authored coordinate `authored_event` judged, as `authored_coordinate_key` spells it "
            "(`chrom:start[:ref]`, the contig empty for a half coordinate). The compiler trusts the "
            "verdict only for a row whose authored coordinate is still this one: an edit made after the "
            "enricher judged, or another table's row under the same key, reads as never judged (RM375)."
        ),
    )
    fetched_at: str | None = Field(
        json_schema_extra=since("0.5.0"),
        default=None,
        description="ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-03T02:03:23Z'). Canonicalized on load; records when this row was last written by a pass, not when the source published anything",
    )
    # ── which release answered (0.8, RM373; EXCLUDED from resolution_signature) ──
    # `source` names the link and `authority` the licensed source behind it; neither names the release,
    # so an old-release answer and a new-release one read alike to every tier (the 0.8 Ensembl
    # migration probe). Per row, because merge-not-clobber makes a table answered by two releases the
    # normal case, and one cell for the table would be false for every module with old rows.
    source_release: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "The release of the snapshot or service that answered this row, as it states its release: "
            "an Ensembl snapshot's `manifest.json` `release_id` (`ensembl-variation-2026_07_13-vep116.0`) "
            "or `release.json` `dataset`, a ClinVar snapshot's `clinvar_<date>`, live Ensembl REST's "
            "data release (`ensembl_116`, from `/info/data`), gnomAD's dataset id. Written only by the "
            "run that answered the row, and never back-filled onto a row it did not answer. Empty means "
            "not recorded (a source that states no release, a row written before 0.8, an authored row), "
            "never the current release. A `reversed` row keeps the release of the row it was reversed "
            "from (RM380)."
        ),
    )

    @field_validator("rsid")
    @classmethod
    def _validate_rsid(cls, v: str | None) -> str | None:
        return validate_rsid(v)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("placement_verdict")
    @classmethod
    def _validate_placement_verdict(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_PLACEMENT_VERDICTS, "placement_verdict")

    @field_validator("authored_event")
    @classmethod
    def _validate_authored_event(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_AUTHORED_EVENT_VERDICTS, "authored_event")

    @field_validator("rsid_current")
    @classmethod
    def _validate_rsid_current(cls, v: str | None) -> str | None:
        return validate_rsid(v)

    @field_validator("rsid_status")
    @classmethod
    def _validate_rsid_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RSID_STATUS, "rsid_status")

    @field_validator("vrs_id")
    @classmethod
    def _validate_vrs_id(cls, v: str | None) -> str | None:
        return validate_vrs_id_list(v)

    @model_validator(mode="after")
    def _vrs_ids_align_with_alts(self) -> "ResolutionRow":
        """`vrs_id` is a parallel array of `alts`, so a desynced pair is caught at load.

        Positional coupling between two columns is the price of not multiplying the table into one row
        per allele, and this is what makes it safe: a human who edits `alts` and forgets `vrs_id` gets a
        refusal here rather than a silently re-pointed identity. (The compiler's `_verify_vrs_ids` is
        the second net — it recomputes every member offline, so a *reordered* pair that still counts
        right is caught there as a mismatch.)

        Only checked when both columns are filled. A `vrs_id` on a row with no `alts` is left alone: the
        enricher never writes one, but a hand-filled table naming an allele it did not record in `alts`
        is under-specified, not contradictory, and refusing it would be this tier inventing a rule.
        """
        if not self.alts or self.vrs_id is None:
            return self
        alts = self.alts.split(",")
        ids = split_vrs_ids(self.vrs_id)
        if len(ids) != len(alts):
            raise ValueError(
                f"vrs_id names {len(ids)} allele id(s) but alts names {len(alts)} allele(s) "
                f"({self.alts!r}) — vrs_id is positionally aligned with alts, one member per ALT "
                f"(empty where no id could be minted), so the two must have the same length"
            )
        return self

    @field_validator("caid")
    @classmethod
    def _validate_caid(cls, v: str | None) -> str | None:
        return validate_caid(v)

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))
