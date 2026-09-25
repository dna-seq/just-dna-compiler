"""Checks over `variants.csv` itself and over the genome build: cross-row validation, the build
restamp, contig ploidy, and the coordinate-on-build check every positional table shares.
"""

from collections.abc import Iterable
from typing import Any, NamedTuple

from just_dna_format.base import derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import (
    builds_containing_position,
    contig_length,
    in_pseudoautosomal_region,
    sole_build_naming_contig,
)

from just_dna_compiler.compiler.table_checks import _examples

# ── Cross-row validation ───────────────────────────────────────────────────────


def _cross_validate_variants(variants: list[VariantRow]) -> tuple[list[str], list[str]]:
    """Validate consistency across variant rows. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    # Only compare rows that actually carry a position. A key seen once with a position and again
    # without one (e.g. an rsid authored with coords on the het row but not the hom row, or a row
    # awaiting resolution) is NOT a conflict — comparing `(None, None)` against a real position was a
    # false positive. Two *positioned* rows for one key that disagree are still an error.
    key_positions: dict[str, tuple[str, int]] = {}
    # `ref` is checked separately from the position because a VA-derived key (0.5) addresses the
    # *place and the alt* — the reference base at a position is a fact of the genome, so VRS does not
    # encode it. That is correct VRS semantics but it drops a guarantee the old `chrom:start:ref:alts`
    # key gave for free: two rows at one position claiming different reference bases used to be two
    # keys, and now they are one. Exactly one of them can be right, so catching it here keeps the
    # authored-typo diagnosis the switch would otherwise have lost.
    key_refs: dict[str, str] = {}
    for row in variants:
        if row.chrom is None or row.start is None:
            continue
        key = row.variant_key
        pos = (row.chrom, row.start)
        if key in key_positions:
            if key_positions[key] != pos:
                errors.append(f"Inconsistent positions for {key}: {key_positions[key]} vs {pos}")
        else:
            key_positions[key] = pos
        if row.ref is not None:
            if key in key_refs:
                if key_refs[key] != row.ref:
                    errors.append(
                        f"Inconsistent reference allele for {key}: {key_refs[key]!r} vs {row.ref!r} "
                        f"at {row.chrom}:{row.start} — the reference base at a position is a single "
                        f"fact, so at most one of these is correct"
                    )
            else:
                key_refs[key] = row.ref

    seen_keys: set[tuple[str, str]] = set()
    for row in variants:
        key = (row.variant_key, row.genotype)
        if key in seen_keys:
            errors.append(f"Duplicate (variant, genotype): ({row.variant_key}, {row.genotype})")
        seen_keys.add(key)

    for row in variants:
        # `state`/`weight` sign consistency (legacy), plus the same check on the new `direction`.
        if row.weight is not None:
            # One code across all four, because one edit clears any of them and the sentence already
            # says which cell disagrees. `state` and `direction` are separate AXES (P5) and stay
            # separate columns; they are not separate *remediations*, which is what a code names.
            if row.state == "risk" and row.weight > 0:
                warnings.append(
                    CodedWarning(
                        "weight_sign_disagrees_with_effect",
                        f"{row.variant_key} genotype {row.genotype}: state='risk' but weight={row.weight} > 0",
                    )
                )
            if row.state == "protective" and row.weight < 0:
                warnings.append(
                    CodedWarning(
                        "weight_sign_disagrees_with_effect",
                        f"{row.variant_key} genotype {row.genotype}: state='protective' but weight={row.weight} < 0",
                    )
                )
            if row.direction == "risk" and row.weight > 0:
                warnings.append(
                    CodedWarning(
                        "weight_sign_disagrees_with_effect",
                        f"{row.variant_key} genotype {row.genotype}: direction='risk' but weight={row.weight} > 0",
                    )
                )
            if row.direction == "protective" and row.weight < 0:
                warnings.append(
                    CodedWarning(
                        "weight_sign_disagrees_with_effect",
                        f"{row.variant_key} genotype {row.genotype}: direction='protective' but weight={row.weight} < 0",
                    )
                )
    return errors, warnings


def _restamp_for_build(variants: list[VariantRow], genome_build: str) -> list[str]:
    """Re-derive `variant_key` against the module's declared build. Returns warnings.

    **The guard existed, was correct, and was never reached.** `derive_variant_key` takes a `build`
    and documents that "any other build falls through to case 3 rather than minting an id that would
    claim the wrong sequence" — but `VariantRow._freeze_identity` runs at row construction, where
    there is no module and therefore no declared build, so it always called the GRCh38 default. A
    module declaring `genome_build: GRCh37` therefore minted GRCh38 VRS allele ids for GRCh37
    coordinates, silently, with no warning anywhere.

    That is an identity corruption, not a cosmetic one, and it goes both ways. `vrs.py` opens by
    promising the opposite — "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids instead of
    silently baking one build into the key". Probed on a real pair: HFE C282Y sits at 6:26092913 on
    GRCh38 and 6:26093141 on GRCh37, and a GRCh37 module at 26093141 minted
    `ga4gh:VA.TWxWV6SkC5-…` — byte-identical to the id a *GRCh38* module claiming that coordinate
    gets, which is a different place in the genome 228 bp away. Two modules about different loci
    shared one content-addressed identity.

    The compiler is where this can be fixed because it is the only tier holding both the row and the
    spec. Re-stamping is not a new concept here — the resolver already re-keys on one-to-many
    expansion — and it is a no-op on GRCh38, which is every module today.
    """
    if genome_build == "GRCh38":
        return []
    restamped = 0
    for row in variants:
        key = derive_variant_key(row.rsid, row.chrom, row.start, row.ref, row.alts, build=genome_build)
        if key != row.variant_key:
            row.variant_key = key
            restamped += 1
    if not restamped:
        return []
    return [
        CodedWarning(
            "non_grch38_variant_keys",
            f"genome_build is {genome_build!r}: GA4GH VRS allele identity is GRCh38-only (RM15), so "
            f"{restamped} variant(s) are keyed by coordinate instead. A coordinate key is "
            f"**build-relative** — it will not join against GRCh38-keyed data, and the same key means a "
            f"different locus on another build. Publish GRCh38 coordinates if the module is meant to "
            f"join against gnomAD, ClinVar or ClinGen.",
        )
    ]


def _check_contig_ploidy(variants: list[VariantRow], genome_build: str = "GRCh38") -> list[str]:
    """Non-diploid guardrail (ROADMAP 0.3 item 5b): MT and Y against a two-allele genotype.

    **Run where `chrom` is final — after resolution, not before.** It used to live inside
    `_cross_validate_variants`, which is called twice: once on the authored rows and once on the
    resolved ones, the second time taking *errors only* ("warnings were already surfaced"). That is
    correct for a warning computed from authored cells and wrong for this one, whose entire input —
    `chrom` — is the thing resolution fills. The result was a check whose coverage depended on
    authoring style rather than on the data: `MT,3243,A/G` written by hand warned, while
    `rs199474657` with genotype `A/G` — the same MELAS variant, the same fake-diploid error, and the
    shape *every drafting provider emits* — was silently unchecked.

    **X is excluded**, as before: it is diploid in XX samples, so a two-allele X row is legitimate and
    warning on it would be pure noise.

    **Y is not the false-positive-free half it was documented to be.** PAR1 and PAR2 recombine with X
    and are diploid in every karyotype, so a two-allele genotype at `Y:359845` is *correct* and the
    old advice ("use a single-allele genotype") would have made the annotation wrong. Real instance:
    `rs6603251` maps to X:359845 **and** Y:359845, and a one-to-many expansion produces the Y row on
    its own — the author never chose it. The premise that "PAR vs non-PAR needs coordinates the format
    does not resolve" was the error: `resolution.csv` resolves exactly that, and the PAR intervals are
    assembly constants of the same class as `vrs.REFGET_GRCh38`.

    So the answer is three-valued (`vrs.in_pseudoautosomal_region`), and the uncertain case is
    reported rather than either asserted or swallowed — the same shape as the `absent` rsID message,
    which names both readings and commits to neither.
    """
    warnings: list[str] = []
    for row in variants:
        if row.chrom not in {"MT", "Y"} or not ("/" in row.genotype or "|" in row.genotype):
            continue
        # MT has no pseudoautosomal region at all, so its verdict never depends on a coordinate.
        par = (
            False
            if row.chrom == "MT"
            else in_pseudoautosomal_region(row.chrom, row.start, build=genome_build)
        )
        if par is True:
            continue
        if par is None:
            # Reachable in practice only for a build with no PAR table: `VariantRow` already refuses
            # `chrom` without `start`, so a Y row always has a position, and an unresolved row has no
            # `chrom` at all and never reaches here. The message therefore names the *build* rather
            # than inventing a missing coordinate, and asserts neither reading — the same shape the
            # `absent` rsID message uses.
            warnings.append(
                CodedWarning(
                    "contig_ploidy_undecidable",
                    f"{row.variant_key} genotype {row.genotype}: chrom=Y with two alleles on build "
                    f"{genome_build!r}, which has no pseudoautosomal table here — so whether this locus "
                    f"is diploid could not be decided. Outside PAR1/PAR2 Y is hemizygous and this should "
                    f"be a single allele (e.g. 'G'); inside them the genotype is right.",
                )
            )
            continue
        warnings.append(
            CodedWarning(
                "contig_ploidy_mismatch",
                f"{row.variant_key} genotype {row.genotype}: chrom={row.chrom} is not diploid here — use "
                f"a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call",
            )
        )
    return warnings


def _coordinate_label(row: Any) -> str:
    """How one offending row is named in a grouped message: its coordinate, and its rsid if it has one.

    Not `variant_key`: for exactly the rows this reports, the key *is* the coordinate (an impossible
    position mints no VRS id), so naming both would print the same numbers twice. The rsid is the one
    thing worth adding, because it is what the author will search their CSV for.
    """
    rsid = getattr(row, "rsid", None)
    return f"{row.chrom}:{row.start}" + (f" ({rsid})" if rsid else "")


class _CoordinateTable(NamedTuple):
    """One table's rows, the build they are recorded under, and who wrote them.

    `authored` decides the **remedy**, not the verdict. "Declare `genome_build: GRCh37`" is sound
    advice about a table a human typed and nonsense about `resolution.csv`, whose build is a per-row
    column on a machine-written sidecar: a GRCh37 module can carry a stale row stamped `GRCh38`, and
    telling its author to declare the build they already declared sends them to the wrong file. The
    fix there is to delete the sidecar and re-run the enricher.
    """

    label: str
    build: str
    authored: bool
    rows: Iterable[Any]


def _check_build_coordinates(tables: Iterable[_CoordinateTable]) -> list[str]:
    """Coordinates that cannot exist in the build they are recorded under (RM48). Errors, both modes.

    An author curating from older literature has hg19/GRCh37 coordinates and the module must be
    GRCh38. Nothing in these packages converts, so the conversion happens off-tool and lands as an
    ordinary authored coordinate carrying no provenance at all — and the two shapes below are the ones
    that are **provably** wrong with no sequence, no network and no provisioned asset, which is what
    puts them in the compiler rather than the enricher:

    - **a position past the end of its contig.** GRCh38's chromosome 1 ends at 248,956,422 and
      GRCh37's runs to 249,250,621, so an un-lifted coordinate in that 294 kb tail is a claim about a
      base that does not exist. When the position *is* inside another tabled build's contig the
      message says which — that is the whole diagnosis, and it costs one dict lookup.
    - **a contig named by only one build.** The 25 primary contigs are spelled identically in both, so
      this is entirely about unplaced scaffolds: `GL000209.1` is GRCh37's and `KI270728.1` is
      GRCh38's, and neither exists in the other. A shared scaffold, a patch, an alt locus or an
      unversioned accession settles nothing and is left alone (`vrs.sole_build_naming_contig`).

    **Error in both modes**, which is the `_cross_validate_variants` inconsistent-reference-allele
    class rather than a mode ladder: `strict` means *reproducible artifact*, and these rows are not
    unreproducible, they are false. Nothing downstream can catch them either — a VRS id minted at an
    impossible position is a correct digest of the wrong input, exactly as the 3,038-row off-by-one
    was.

    Findings are grouped by **reason** (table, contig, and which other build explains it) rather than
    by row, because a wrong-build panel produces one of these per variant: 2,400 rows disagreeing one
    by one reads as hopeless, while "2,400 rows carry GRCh37 coordinates" is a one-line fix. The
    `summarize_ref_mismatches` shape, on the offline half.

    Each table arrives as a `_CoordinateTable` — the build travels *per table* because
    `resolution.csv` records its own on every row and a module's yaml speaks only for the authored
    ones; comparing a resolution row against the module's declared build would be the wrong question
    for a row that says which build it is in. `authored` picks the remedy for the same reason.
    """
    beyond: dict[tuple[str, str, bool, str, tuple[str, ...]], list[str]] = {}
    misnamed: dict[tuple[str, str, bool, str, str], list[str]] = {}
    for label, build, authored, rows in tables:
        for row in rows:
            chrom, start = getattr(row, "chrom", None), getattr(row, "start", None)
            if chrom is None:
                continue
            elsewhere = sole_build_naming_contig(chrom)
            if elsewhere is not None and elsewhere != build:
                misnamed.setdefault((label, build, authored, str(chrom), elsewhere), []).append(
                    _coordinate_label(row)
                )
                continue
            length = contig_length(chrom, build)
            if start is None or length is None or start <= length:
                continue
            others = tuple(b for b in builds_containing_position(chrom, start) if b != build)
            beyond.setdefault((label, build, authored, str(chrom), others), []).append(_coordinate_label(row))

    errors: list[str] = []
    for (label, build, authored, chrom, others), found in beyond.items():
        length = contig_length(chrom, build)
        if others:
            elsewhere = others[0]
            explanation = (
                f"every one of those positions is inside {elsewhere}'s {chrom} "
                f"({contig_length(chrom, elsewhere):,} bp), so this reads as an un-lifted "
                f"{elsewhere} coordinate under a {build} heading. Recover the rs-numbers with "
                f"`just-dna-enricher hint recover --chrom {chrom} --start …` and author those "
                f"instead — an rs-number resolves into a coordinate the compiler can cross-examine, "
                f"where a converted position is its own only witness. Or "
                + _build_remedy(authored, elsewhere)
            )
        else:
            explanation = (
                f"no build this compiler knows has a contig {chrom} that long, so the position is "
                f"wrong in every frame — check the contig and the position together"
            )
        errors.append(
            f"{label}: {len(found)} row(s) place a variant past the end of {chrom} on {build} "
            f"({length:,} bp) — {explanation} ({_examples(found)})"
        )
    for (label, build, authored, chrom, elsewhere), found in misnamed.items():
        errors.append(
            f"{label}: {len(found)} row(s) name contig {chrom}, which is a top-level sequence of "
            f"{elsewhere} and of no other build this compiler knows, while the rows are recorded as "
            f"{build}. A coordinate on it means nothing here: fix the contig, or "
            + _build_remedy(authored, elsewhere)
            + f" ({_examples(found)})"
        )
    return errors


def _build_remedy(authored: bool, elsewhere: str) -> str:
    """Where the build is actually declared for this table — which is not the same file for both."""
    if authored:
        return f"declare `genome_build: {elsewhere}` if the whole module is on that assembly."
    return (
        f"delete the sidecar and re-run `just-dna-enricher enrich` if these rows are stale — the "
        f"build is a per-row column here, not the module's declaration, so a module already "
        f"declaring {elsewhere} can still carry rows stamped otherwise."
    )
