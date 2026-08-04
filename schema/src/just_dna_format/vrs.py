"""GA4GH VRS allele identity — `derive_vrs_allele_id`, the sibling of `base.derive_variant_key`.

A VRS **Allele id** (`ga4gh:VA.<digest>`) is a *content-addressed* name for one allele at one place
on one reference sequence. It is the identity RM15 was waiting for: unlike a bare `chrom:start:ref`,
it **names its build**, because the sequence is addressed by its refget accession — the digest *of the
reference sequence itself* — so GRCh38 and GRCh37 mint distinct, correctly non-colliding ids instead
of silently baking one build into the key.

**Stdlib only.** The identification algorithm is `sha512t24u` over a compact canonical JSON, which is
~20 lines of `hashlib` + `base64` + `json`. The format tier therefore gains **no dependency** (it stays
pydantic + cryptography, CONSTITUTION Goal 2) and a verify-only consumer can recompute the identity
offline. This was probed, not assumed: the ids this module mints are byte-identical to the ones the
live gnomAD API returns (see `schema/tests/test_vrs.py`, which asserts against recorded ground truth).

**Substitutions only, on purpose.** `derive_vrs_allele_id` mints for a single-base substitution and
returns `None` for everything else (indel, MNV, multi-allelic cell, or a row with no coordinate). A
VRS allele id is defined over the *fully justified* (normalized) allele; for an SNV, normalization is
a provable no-op — there is no shared prefix or suffix to trim and nothing to shift — so the id is
computable offline and interoperable. For an indel, justification needs the reference *sequence*,
which this tier has no access to and will never fetch (Principle 2). Minting an unjustified indel id
would emit a `ga4gh:VA.…` string that *looks* interoperable and is not, which is worse than minting
nothing. Indel ids are minted upstream in `just-dna-enricher`'s `[dev]` extras (which do have a
sequence proxy) and passed through as data, exactly as gnomAD's `variantId` is.
"""

import base64
import hashlib
import json
import re
from typing import Optional

# Namespace prefixes of the two GA4GH-shaped cross-references carried on a resolution row.
VRS_ALLELE_PREFIX: str = "ga4gh:VA."
# `ga4gh:VA.` + a 32-char base64url `sha512t24u` digest. Also accepts the other identifiable VRS
# types a producer might hand us verbatim, so a validator rejects a *malformed* value rather than an
# unfamiliar-but-well-formed one.
VRS_ID_PATTERN: re.Pattern[str] = re.compile(r"^ga4gh:(VA|SL|SQ|CX|CN)\.[A-Za-z0-9_-]{32}$")
# ClinGen Allele Registry canonical allele id.
CAID_PATTERN: re.Pattern[str] = re.compile(r"^CA\d+$")

# The VRS spec version whose serialization `derive_vrs_allele_id` implements. Stored beside a minted
# id (`ResolutionRow.vrs_spec`) to disambiguate an *embedded location* id, not because the allele id
# drifts — the `VA.` digest for a substitution is identical under 1.x and 2.0, which is why gnomAD's
# (1.x-shaped) payload and this 2.0 implementation agree byte-for-byte.
VRS_SPEC_VERSION: str = "2.0"

# ── The GRCh38 refget accession per primary contig ─────────────────────────────────────────────
# A refget accession IS the identity of a reference sequence (`SQ.` + `sha512t24u` of the uppercased
# sequence), which is what makes a VRS allele id build-naming rather than build-ambiguous. Committed
# as a constant so minting needs no `seqrepo`, no sequence store, and no network; re-derived from the
# public seqrepo REST by an `@integration` test so a wrong digest cannot silently ship (these were
# fetched from that service, and chr1/chr11 are independently confirmed by the recorded-ground-truth
# ids in `schema/tests/test_vrs.py` — a wrong accession could not produce a matching allele id).
#
# Primary assembly only: the 22 autosomes, X, Y and MT. An alt contig / scaffold / patch is not here,
# so it mints nothing rather than minting under a guessed accession. Adding GRCh37 (or any other
# build) is a second table beside this one — that is RM15's remaining extension, and the reason this
# is keyed by build rather than assumed.
REFGET_GRCh38: dict[str, str] = {
    "1": "SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
    "2": "SQ.pnAqCRBrTsUoBghSD1yp_jXWSmlbdh4g",
    "3": "SQ.Zu7h9AggXxhTaGVsy7h_EZSChSZGcmgX",
    "4": "SQ.HxuclGHh0XCDuF8x6yQrpHUBL7ZntAHc",
    "5": "SQ.aUiQCzCPZ2d0csHbMSbh2NzInhonSXwI",
    "6": "SQ.0iKlIQk2oZLoeOG9P1riRU6hvL5Ux8TV",
    "7": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
    "8": "SQ.209Z7zJ-mFypBEWLk4rNC6S_OxY5p7bs",
    "9": "SQ.KEO-4XBcm1cxeo_DIQ8_ofqGUkp4iZhI",
    "10": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
    "11": "SQ.2NkFm8HK88MqeNkCgj78KidCAXgnsfV1",
    "12": "SQ.6wlJpONE3oNb4D69ULmEXhqyDZ4vwNfl",
    "13": "SQ._0wi-qoDrvram155UmcSC-zA5ZK4fpLT",
    "14": "SQ.eK4D2MosgK_ivBkgi6FVPg5UXs1bYESm",
    "15": "SQ.AsXvWL1-2i5U_buw6_niVIxD6zTbAuS6",
    "16": "SQ.yC_0RBj3fgBlvgyAuycbzdubtLxq-rE0",
    "17": "SQ.dLZ15tNO1Ur0IcGjwc3Sdi_0A6Yf4zm7",
    "18": "SQ.vWwFhJ5lQDMhh-czg06YtlWqu0lvFAZV",
    "19": "SQ.IIB53T8CNeJJdUqzn9V_JnRtQadwWCbl",
    "20": "SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
    "21": "SQ.5ZUqxCmDDgN4xTRbaSjN8LwgZironmB8",
    "22": "SQ.7B7SHsmchAR0dFcDCuSFjJAo7tX87krQ",
    "X": "SQ.w0WZEvgJF0zf_P4yyTzjjv9oW1z61HHP",
    "Y": "SQ.8_liLu1aycC0tPQPFmUaGXJLDs5SbPZ5",
    "MT": "SQ.k3grVkjY-hoWcCUojHw6VU6GE3MZ8Sct",
}

# Contig length per accession, so a coordinate past the end of a chromosome mints nothing rather than
# minting a well-formed id for a place that does not exist. Same source as the accessions above.
REFGET_GRCh38_LENGTHS: dict[str, int] = {
    "1": 248956422, "2": 242193529, "3": 198295559, "4": 190214555, "5": 181538259,
    "6": 170805979, "7": 159345973, "8": 145138636, "9": 138394717, "10": 133797422,
    "11": 135086622, "12": 133275309, "13": 114364328, "14": 107043718, "15": 101991189,
    "16": 90338345, "17": 83257441, "18": 80373285, "19": 58617616, "20": 64444167,
    "21": 46709983, "22": 50818468, "X": 156040895, "Y": 57227415, "MT": 16569,
}

_BASES: frozenset[str] = frozenset("ACGT")


class UnsupportedBuildError(ValueError):
    """Raised when a caller asks for a build this module has no refget table for (RM15)."""


def sha512t24u(blob: bytes) -> str:
    """The GA4GH `sha512t24u` digest: unpadded base64url of the first 24 bytes of SHA-512.

    24 bytes is chosen so the base64 encoding is exactly 32 characters with no padding — which is why
    the digest never carries a `=` and why `VRS_ID_PATTERN` can pin the length.
    """
    return base64.urlsafe_b64encode(hashlib.sha512(blob).digest()[:24]).decode("ascii")


def _canonical(obj: dict) -> bytes:
    """VRS canonical JSON: sorted keys, no whitespace, UTF-8 — the bytes the digest is taken over."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_chrom(chrom: Optional[str]) -> Optional[str]:
    """Fold a chromosome label to this module's key form (`chr7` → `7`, `M`/`chrM` → `MT`)."""
    if chrom is None:
        return None
    value = chrom.strip()
    if not value:
        return None
    value = value.removeprefix("chr").removeprefix("CHR").removeprefix("Chr")
    upper = value.upper()
    if upper in ("M", "MT"):
        return "MT"
    return upper if upper in ("X", "Y") else value


# ── The pseudoautosomal regions of GRCh38 ──────────────────────────────────────────────────────
# X and Y share two homologous stretches that recombine at meiosis, so a locus inside one is present
# in **two copies in every karyotype** — diploid in XX and in XY alike. 1-based inclusive, matching the
# convention the rest of this pipeline stores (Ensembl/CPIC/PharmVar positions go in unconverted).
#
# These are assembly constants, exactly like `REFGET_GRCh38` above: fixed properties of a named build,
# not curated data that goes stale, so holding them here is not the un-injected-reference mistake
# (RM21). They live in the format tier because the *compiler* needs them offline — the non-diploid
# guardrail cannot otherwise tell a genuinely hemizygous Y locus from a PAR one.
PAR_GRCh38: dict[str, tuple[tuple[int, int], ...]] = {
    "X": ((10_001, 2_781_479), (155_701_383, 156_030_895)),
    "Y": ((10_001, 2_781_479), (56_887_903, 57_217_415)),
}


def in_pseudoautosomal_region(
    chrom: Optional[str], start: Optional[int], *, build: str = "GRCh38"
) -> Optional[bool]:
    """Is this locus in a PAR? **Three-valued** — `True`, `False`, or `None` for "cannot say".

    `None` when there is no coordinate, when the contig is not X or Y, or when the build is one this
    table does not describe. A caller must not read `None` as `False`: "this row has no position" and
    "this position is outside the PAR" are different facts, and the second licenses a claim about
    ploidy that the first does not.

    Unlike `refget_accession` this does **not** raise on another build. That function answers a
    question whose wrong answer would corrupt an identity, so silence is unacceptable; this one feeds
    a warning, where the honest degradation is to withhold it.
    """
    if start is None or build != "GRCh38":
        return None
    regions = PAR_GRCh38.get(normalize_chrom(chrom) or "")
    if regions is None:
        return None
    return any(low <= start <= high for low, high in regions)


#: The other contig of a pseudoautosomal pair.
_PAR_PARTNER_CONTIG = {"X": "Y", "Y": "X"}


def par_partner(
    chrom: Optional[str], start: Optional[int], *, build: str = "GRCh38"
) -> Optional[tuple[str, int]]:
    """Where this pseudoautosomal locus is spelled on the *other* sex contig.

    Returns `(contig, position)` — `("Y", 640851)` for `("X", 640851)` — or `None`, which is the
    withhold answer this module uses everywhere: no coordinate, a contig that is not X or Y, a locus
    outside both PARs, or a build with no PAR table. A caller must not read `None` as "there is no
    partner", only as "this function did not name one".

    The arithmetic is an index-matched offset between the two contigs' intervals, which is well-defined
    because GRCh38's Y PAR *is* a copy of the X PAR: the paired intervals have equal length, so PAR1
    maps at offset 0 (X:640851 ↔ Y:640851) and PAR2 at a constant 98,813,480 (X:155770036 ↔
    Y:56956556). A test pins the equal-length property over the table itself, so adding a build whose
    intervals do not pair cannot silently corrupt the mapping.

    **Position agreement is a necessary condition, never a sufficient one.** Two loci at partner
    coordinates are the same place, but a caller deciding they are the same *variant* must also compare
    alleles — this function knows nothing about `ref`/`alts`, and fusing on geometry alone would merge
    two different variants that happen to sit opposite each other.
    """
    if start is None or build != "GRCh38":
        return None
    contig = normalize_chrom(chrom) or ""
    other = _PAR_PARTNER_CONTIG.get(contig)
    if other is None:
        return None
    here, there = PAR_GRCh38[contig], PAR_GRCh38[other]
    for (low, high), (other_low, _other_high) in zip(here, there):
        if low <= start <= high:
            return other, start - low + other_low
    return None


def refget_accession(chrom: Optional[str], build: str = "GRCh38") -> Optional[str]:
    """The refget accession for a contig on `build`, or `None` for a contig outside the table.

    Raises `UnsupportedBuildError` for a build with no table — a caller asking for GRCh37 today gets a
    clear "not built yet" rather than a silently GRCh38-flavoured answer (RM15).
    """
    if build != "GRCh38":
        raise UnsupportedBuildError(
            f"no refget table for build {build!r}; VRS minting is GRCh38-only today (RM15 tracks "
            f"the multi-build extension — a second table beside REFGET_GRCh38)"
        )
    return REFGET_GRCh38.get(normalize_chrom(chrom) or "")


def sequence_location_digest(
    chrom: Optional[str], start: int, end: int, *, build: str = "GRCh38"
) -> Optional[str]:
    """The bare `sha512t24u` of a VRS `SequenceLocation` over interbase `[start, end)`.

    `start`/`end` are **interbase** (0-based, half-open) — VRS's coordinate convention, not VCF's.
    Returns `None` when the contig has no accession. The full CURIE for this digest would be
    `ga4gh:SL.<digest>`; the bare digest is what an enclosing Allele embeds.
    """
    accession = refget_accession(chrom, build)
    if accession is None:
        return None
    return sha512t24u(
        _canonical(
            {
                "end": end,
                "sequenceReference": {"refgetAccession": accession, "type": "SequenceReference"},
                "start": start,
                "type": "SequenceLocation",
            }
        )
    )


def is_substitution(ref: Optional[str], alt: Optional[str]) -> bool:
    """Whether `(ref, alt)` is a single-base substitution — the normalization-invariant case.

    This is exactly the class `derive_vrs_allele_id` will mint: one ACGT base to a *different* one ACGT
    base. For it, VRS's full justification is a provable no-op (nothing to trim, nothing to shift), so
    the id computed here equals the id a normalizing implementation with sequence access would compute.
    """
    if ref is None or alt is None:
        return False
    ref_u, alt_u = ref.strip().upper(), alt.strip().upper()
    return len(ref_u) == 1 and len(alt_u) == 1 and ref_u != alt_u and {ref_u, alt_u} <= _BASES


def derive_vrs_allele_id(
    chrom: Optional[str],
    start: Optional[int],
    ref: Optional[str],
    alt: Optional[str],
    *,
    build: str = "GRCh38",
) -> Optional[str]:
    """The `ga4gh:VA.…` allele id for a resolved substitution, or `None` when it cannot be minted.

    `start` is the **1-based VCF position** (the convention `ResolutionRow.start` and the Ensembl /
    ClinVar snapshots already use); the interbase conversion happens here, once, so no caller has to
    remember it.

    Returns `None` — never raises, never guesses — when the row is not a mintable substitution:

    - no coordinate (an rsid-only row, pre-resolution): there is nothing to address;
    - an indel or MNV: justification needs the reference sequence (see the module docstring);
    - a multi-allelic cell (`alt` carrying a comma): a VA names *one* allele, so the caller must split
      first — silently picking one would be a data error wearing an id;
    - a contig outside the primary assembly, or a position past the end of it.

    The digest is taken over the VRS Allele serialization, in which the location appears as its **own
    digest** (not inlined and not as a `ga4gh:SL.` CURIE) — that exact shape is what reproduces the ids
    gnomAD serves, and the test suite pins it against recorded ground truth rather than trusting the
    reading of any spec text.
    """
    if start is None or not is_substitution(ref, alt):
        return None
    if start < 1:
        return None
    contig = normalize_chrom(chrom)
    length = REFGET_GRCh38_LENGTHS.get(contig or "") if build == "GRCh38" else None
    if length is not None and start > length:
        return None
    # VCF POS is 1-based inclusive; VRS is 0-based half-open. A 1-base ref at POS p spans [p-1, p).
    location = sequence_location_digest(contig, start - 1, start, build=build)
    if location is None:
        return None
    allele = {
        "location": location,
        "state": {"sequence": (alt or "").strip().upper(), "type": "LiteralSequenceExpression"},
        "type": "Allele",
    }
    return VRS_ALLELE_PREFIX + sha512t24u(_canonical(allele))


def validate_vrs_id(value: Optional[str], field_name: str = "vrs_id") -> Optional[str]:
    """Validate an optional GA4GH VRS identifier (`ga4gh:<TYPE>.<32-char digest>`)."""
    if value is not None and not VRS_ID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a GA4GH VRS identifier like "
            f"ga4gh:VA.JGrSjQEcYOJ14vlkvm7sIyYSgHfpC5UG, got: {value!r}"
        )
    return value


def validate_caid(value: Optional[str], field_name: str = "caid") -> Optional[str]:
    """Validate an optional ClinGen Allele Registry canonical allele id (`CA<digits>`)."""
    if value is not None and not CAID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a ClinGen canonical allele id like CA125138, got: {value!r}"
        )
    return value
