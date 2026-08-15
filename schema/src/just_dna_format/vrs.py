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
from collections.abc import Sequence

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

# ── Contig geometry per build: what a coordinate could possibly mean (RM48) ────────────────────
# Assembly constants of the same class as `REFGET_GRCh38` and `PAR_GRCh38` above — fixed properties
# of a named build, not curated data that goes stale — and here for the same reason: the *compiler*
# needs them offline, and a wrong-build coordinate is decidable with no sequence, no network and no
# provisioned asset.
#
# **These mint nothing.** There is deliberately no `REFGET_GRCh37` beside them: an accession is what
# a content-addressed identity is a function of, and a second build's identity is RM15's design
# round, not this one's. A length and a name answer "could this coordinate exist?", which is a
# question about a claim rather than a name for a variant, so `refget_accession` keeps raising for
# GRCh37 exactly as before.
#
# Numbers and names taken from Ensembl's `/info/assembly/homo_sapiens` on both the current and the
# permanent GRCh37 service (probed 2026-08-13, GRCh38.p14 / GRCh37.p13). A network-gated test
# re-derives all four tables from those services, so a wrong number cannot silently ship.
PRIMARY_CONTIG_LENGTHS: dict[str, dict[str, int]] = {
    "GRCh38": REFGET_GRCh38_LENGTHS,
    "GRCh37": {
        "1": 249250621, "2": 243199373, "3": 198022430, "4": 191154276, "5": 180915260,
        "6": 171115067, "7": 159138663, "8": 146364022, "9": 141213431, "10": 135534747,
        "11": 135006516, "12": 133851895, "13": 115169878, "14": 107349540, "15": 102531392,
        "16": 90354753, "17": 81195210, "18": 78077248, "19": 59128983, "20": 63025520,
        "21": 48129895, "22": 51304566, "X": 155270560, "Y": 59373566, "MT": 16569,
    },
}

# Top-level contigs a build has and no other build in this table does — the *difference*, which is
# exactly the predicate "this name exists only in the other build" and nothing wider. The full
# per-build name sets were the other candidate and are worse here: they would invite the claim "this
# contig is not in the declared build", which is false for a patch scaffold or an alt locus (neither
# appears in a top-level listing), and a guess of that kind becomes a false accusation about a row.
#
# The **primary 25 names are identical across both builds**, so the lengths above cannot decide a
# name question and these scaffolds are the whole of it: without them the wrong-build-contig-name
# hypothesis has no instantiation at all. Note that a version suffix is load-bearing —
# `GL000205.1` is GRCh37's and `GL000205.2` is GRCh38's — so a bare `GL000205` is in neither set and
# is deliberately left undecided.
CONTIGS_ONLY_IN: dict[str, frozenset[str]] = {
    "GRCh38": frozenset({
        "GL000008.2", "GL000009.2", "GL000205.2", "GL000216.2", "KI270302.1", "KI270303.1",
        "KI270304.1", "KI270305.1", "KI270310.1", "KI270311.1", "KI270312.1", "KI270315.1",
        "KI270316.1", "KI270317.1", "KI270320.1", "KI270322.1", "KI270329.1", "KI270330.1",
        "KI270333.1", "KI270334.1", "KI270335.1", "KI270336.1", "KI270337.1", "KI270338.1",
        "KI270340.1", "KI270362.1", "KI270363.1", "KI270364.1", "KI270366.1", "KI270371.1",
        "KI270372.1", "KI270373.1", "KI270374.1", "KI270375.1", "KI270376.1", "KI270378.1",
        "KI270379.1", "KI270381.1", "KI270382.1", "KI270383.1", "KI270384.1", "KI270385.1",
        "KI270386.1", "KI270387.1", "KI270388.1", "KI270389.1", "KI270390.1", "KI270391.1",
        "KI270392.1", "KI270393.1", "KI270394.1", "KI270395.1", "KI270396.1", "KI270411.1",
        "KI270412.1", "KI270414.1", "KI270417.1", "KI270418.1", "KI270419.1", "KI270420.1",
        "KI270422.1", "KI270423.1", "KI270424.1", "KI270425.1", "KI270429.1", "KI270435.1",
        "KI270438.1", "KI270442.1", "KI270448.1", "KI270465.1", "KI270466.1", "KI270467.1",
        "KI270468.1", "KI270507.1", "KI270508.1", "KI270509.1", "KI270510.1", "KI270511.1",
        "KI270512.1", "KI270515.1", "KI270516.1", "KI270517.1", "KI270518.1", "KI270519.1",
        "KI270521.1", "KI270522.1", "KI270528.1", "KI270529.1", "KI270530.1", "KI270538.1",
        "KI270539.1", "KI270544.1", "KI270548.1", "KI270579.1", "KI270580.1", "KI270581.1",
        "KI270582.1", "KI270583.1", "KI270584.1", "KI270587.1", "KI270588.1", "KI270589.1",
        "KI270590.1", "KI270591.1", "KI270593.1", "KI270706.1", "KI270707.1", "KI270708.1",
        "KI270709.1", "KI270710.1", "KI270711.1", "KI270712.1", "KI270713.1", "KI270714.1",
        "KI270715.1", "KI270716.1", "KI270717.1", "KI270718.1", "KI270719.1", "KI270720.1",
        "KI270721.1", "KI270722.1", "KI270723.1", "KI270724.1", "KI270725.1", "KI270726.1",
        "KI270727.1", "KI270728.1", "KI270729.1", "KI270730.1", "KI270731.1", "KI270732.1",
        "KI270733.1", "KI270734.1", "KI270735.1", "KI270736.1", "KI270737.1", "KI270738.1",
        "KI270739.1", "KI270740.1", "KI270741.1", "KI270742.1", "KI270743.1", "KI270744.1",
        "KI270745.1", "KI270746.1", "KI270747.1", "KI270748.1", "KI270749.1", "KI270750.1",
        "KI270751.1", "KI270752.1", "KI270753.1", "KI270754.1", "KI270755.1", "KI270756.1",
        "KI270757.1",
    }),
    "GRCh37": frozenset({
        "GL000191.1", "GL000192.1", "GL000193.1", "GL000196.1", "GL000197.1", "GL000198.1",
        "GL000199.1", "GL000200.1", "GL000201.1", "GL000202.1", "GL000203.1", "GL000204.1",
        "GL000205.1", "GL000206.1", "GL000207.1", "GL000209.1", "GL000210.1", "GL000211.1",
        "GL000212.1", "GL000215.1", "GL000216.1", "GL000217.1", "GL000222.1", "GL000223.1",
        "GL000227.1", "GL000228.1", "GL000229.1", "GL000230.1", "GL000231.1", "GL000232.1",
        "GL000233.1", "GL000234.1", "GL000235.1", "GL000236.1", "GL000237.1", "GL000238.1",
        "GL000239.1", "GL000240.1", "GL000241.1", "GL000242.1", "GL000243.1", "GL000244.1",
        "GL000245.1", "GL000246.1", "GL000247.1", "GL000248.1", "GL000249.1",
    }),
}

#: Case-folded name → the one build that names it. Built once, because an author who types
#: `gl000209.1` has made a spelling slip and not a build mistake, and a case-sensitive miss here
#: would silently withhold the diagnosis they need.
_BUILD_BY_EXCLUSIVE_CONTIG: dict[str, str] = {
    name.casefold(): build for build, names in CONTIGS_ONLY_IN.items() for name in names
}


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


def normalize_chrom(chrom: str | None) -> str | None:
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
    chrom: str | None, start: int | None, *, build: str = "GRCh38"
) -> bool | None:
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
    chrom: str | None, start: int | None, *, build: str = "GRCh38"
) -> tuple[str, int] | None:
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
    # `strict=True` on purpose: the pairing is **index-matched**, PAR1 to PAR1 and PAR2 to PAR2, so a
    # table that ever gained an interval on one contig and not the other must fail loudly. Truncating
    # would keep PAR1 working and silently stop answering for PAR2 — the exact asymmetry that makes a
    # PAR bug hard to see, since PAR1 is the one every casual test uses.
    for (low, high), (other_low, _other_high) in zip(here, there, strict=True):
        if low <= start <= high:
            return other, start - low + other_low
    return None


def contig_length(chrom: str | None, build: str = "GRCh38") -> int | None:
    """How long this contig is on `build`, or `None` for a question this table cannot answer.

    `None` covers three quite different unknowns and deliberately reads as one: no contig given, a
    build with no table, and a name that is not a *primary* contig of that build (a scaffold, a patch,
    an alt locus). All three mean the same thing to a caller — nothing may be concluded about a
    position on it — and the three-valued rule says withhold rather than guess a bound.

    Unlike `refget_accession` this does **not** raise for an untabled build, for the same reason
    `in_pseudoautosomal_region` does not: that function answers a question whose wrong answer would
    corrupt an identity, while this one feeds a *diagnosis*, where the honest degradation is silence.
    """
    lengths = PRIMARY_CONTIG_LENGTHS.get(build)
    if lengths is None:
        return None
    return lengths.get(normalize_chrom(chrom) or "")


def builds_containing_position(chrom: str | None, start: int | None) -> tuple[str, ...]:
    """Every tabled build whose `chrom` reaches `start`, in sorted order.

    The wrong-build half of the diagnosis: a position past the end of GRCh38's chromosome 1 that is
    comfortably inside GRCh37's is not merely impossible, it is *impossible in a way that names its
    cause*. Empty means no tabled build has a contig of that name long enough — which is a different
    finding, and a caller must render the two separately.

    Only the **upper** bound is consulted. VCF's telomere convention writes POS 0 for a variant before
    the first base of a contig, so a low position is not evidence of anything and this function says
    nothing about one.
    """
    if start is None:
        return ()
    return tuple(
        build
        for build in sorted(PRIMARY_CONTIG_LENGTHS)
        if (length := contig_length(chrom, build)) is not None and start <= length
    )


def sole_build_naming_contig(chrom: str | None) -> str | None:
    """The build that alone names this contig, or `None` when that cannot be established.

    `None` is the answer for every name the tables do not settle: the 25 primary contigs (identical
    across both builds), a scaffold both builds carry (`GL000194.1`), a patch or alt locus (in no
    top-level listing at all), and an unversioned accession (`GL000205` — the suffix is what
    separates GRCh37's `.1` from GRCh38's `.2`). Withholding on all of those is the point: a name this
    table cannot place is not evidence of a wrong build, and treating it as such would put a false
    accusation on a correct row.
    """
    if chrom is None:
        return None
    return _BUILD_BY_EXCLUSIVE_CONTIG.get((normalize_chrom(chrom) or "").casefold())


def _build_has_refget_table(build: str | None) -> bool:
    """The one predicate `refget_accession` and `refget_supports_build` both read (R2-10).

    They disagreed on `None` and `""` — one raised, the other answered `True` while its docstring
    said it answers *"the question `refget_accession` raises on"*. Writing the condition twice is
    what let them; RM15 adds a second table, which is when a third copy would appear.
    """
    return build == "GRCh38"


def refget_accession(chrom: str | None, build: str = "GRCh38") -> str | None:
    """The refget accession for a contig on `build`, or `None` for a contig outside the table.

    Raises `UnsupportedBuildError` for a build with no table — a caller asking for GRCh37 today gets a
    clear "not built yet" rather than a silently GRCh38-flavoured answer (RM15). An explicitly passed
    `None` or `""` is such a build: the GRCh38 default lives in this signature, so *omitting* the
    argument is the default and *handing over an empty one* is a caller who has not established the
    build. `refget_supports_build` reads the same predicate and says so first.
    """
    if not _build_has_refget_table(build):
        raise UnsupportedBuildError(
            f"no refget table for build {build!r}; VRS minting is GRCh38-only today (RM15 tracks "
            f"the multi-build extension — a second table beside REFGET_GRCh38)"
        )
    return REFGET_GRCh38.get(normalize_chrom(chrom) or "")


def refget_supports_build(build: str | None) -> bool:
    """Is there a refget table for this assembly at all — the question `refget_accession` raises on.

    Separate from `refget_accession` because the two answer different things and only one of them is
    a per-contig question. `refget_accession(chrom, build)` has three outcomes — an accession, `None`
    for a contig outside the table, and `UnsupportedBuildError` for an assembly with no table — and a
    caller that wants the third has to raise and catch an exception to ask a yes/no question. Worse,
    the two negatives then arrive at the same `except`/`is None` and get treated alike, which is how
    `sequences.verify_reference_alleles` came to swallow a whole GRCh37 module row by row and report
    the pass as having run: an unbuilt assembly is a statement about the module, an unmapped contig is
    a statement about one row.

    Kept beside the table rather than in the enricher, for the reason `PAR_GRCh38` is here: which
    assemblies have a refget table is a property of this tier's constants, and a copy elsewhere is a
    second list to keep in step when RM15 adds the second table.

    **`None` and `""` answer `False`, and they answered `True` until R2-10.** The docstring above
    claims to answer *"the question `refget_accession` raises on"*, and for those two inputs it was
    answering the opposite of what that function does — a printed claim the code did not honour, in
    the tier the other two build on, and precisely on the guard a caller reaches for *in order to*
    avoid the exception. Latent, because the one caller filters `if row.genome_build` first.

    The old reasoning was *"an unset build is the format's default, not an unbuilt assembly"*, and it
    imports a fact about the **spec** layer into the **identity** layer. `ModuleSpecConfig.genome_build`
    does default to GRCh38, and so does each of these functions' own *signature* — but an explicit
    `None` handed to a build parameter is not an omitted argument, it is a caller who did not thread
    the row's build through, which is the bug class `test_build_call_sites.py` walks the AST to
    prevent. Every other build gate in this module already reads it that way (`in_pseudoautosomal_region`,
    `par_partner`, `contig_length`, and the two minting functions all withhold on anything that is not
    literally `GRCh38`), so answering `True` here made this one function the outlier. Both sides now
    read the same predicate, so they cannot drift apart again.
    """
    return _build_has_refget_table(build)


def sequence_location_digest(
    chrom: str | None, start: int, end: int, *, build: str = "GRCh38"
) -> str | None:
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


def is_substitution(ref: str | None, alt: str | None) -> bool:
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
    chrom: str | None,
    start: int | None,
    ref: str | None,
    alt: str | None,
    *,
    build: str = "GRCh38",
) -> str | None:
    """The `ga4gh:VA.…` allele id for a resolved substitution, or `None` when it cannot be minted.

    `start` is the **1-based VCF position** (the convention `ResolutionRow.start` and the Ensembl /
    ClinVar snapshots already use); the interbase conversion happens here, once, so no caller has to
    remember it.

    Returns `None` — never guesses — when the row is not a mintable substitution:

    - no coordinate (an rsid-only row, pre-resolution): there is nothing to address;
    - an indel or MNV: justification needs the reference sequence (see the module docstring);
    - a multi-allelic cell (`alt` carrying a comma): a VA names *one* allele, so the caller must split
      first — silently picking one would be a data error wearing an id. "Split first" is the whole
      instruction: refusing to *pick* is not a reason to mint *nothing*, which is the mistake
      `split_vrs_ids`/`join_vrs_ids` exist to stop a caller making (see their docstrings);
    - a contig outside the primary assembly, or a position past the end of it.

    It **raises** `UnsupportedBuildError` for exactly one input: a `build` with no refget table (today,
    anything but GRCh38). That is not an oversight and must not be softened to `None` — `None` here
    means "this row is not mintable", a per-row fact, while an unknown build means the caller's whole
    frame of reference is unavailable, and answering `None` would let a GRCh37 module quietly compile
    with no identities rather than being told minting is GRCh38-only (RM15). Every call site therefore
    catches it and turns it into its own kind of report: `compiler._recompute_vrs_id` into an
    "unverifiable" reason, `enricher.vrs.VrsMinter.mint` into an unmintable row.

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


def split_vrs_ids(value: str | None) -> list[str | None]:
    """A comma-joined `vrs_id` cell → one entry per ALT, `None` where no id was minted.

    A VRS allele id names **one** allele, and `alts` is a column that may name several. Two ways to
    reconcile that, and only one of them is honest. The first — mint nothing for a multi-allelic row —
    is what this codebase did, borrowing `derive_vrs_allele_id`'s refusal to *pick* an allele and
    applying it to a column where nothing is being picked. It cost the id on 909 of 1,613 rows in one
    real module while every input needed to compute all 2,110 of them sat in the same row.

    The second is this: `vrs_id` is a **parallel array of `alts`**, so member *i* names alt *i*. A hole
    (an empty member) is a real value — "this allele's id could not be minted here" — because a
    substitution and an indel can share one site and only one of them mints offline. Losing the whole
    row's ids to the indel beside them would be the same abstention one level down.

    A single-alt row degenerates to a bare id, byte-identical to what every existing file carries, so
    this widening reaches no module that does not need it. It also moves no signature: `vrs_id` is
    outside `RESOLUTION_FACT_FIELDS` and `reverse_module` does not re-emit it.
    """
    if not value:
        return []
    return [member.strip() or None for member in value.split(",")]


def join_vrs_ids(ids: Sequence[str | None]) -> str | None:
    """Per-allele ids → the comma-joined cell, or `None` when not one of them was minted.

    Holes are kept, so position is preserved; an all-holes result is `None` rather than `",,"`, since
    a row that minted nothing is exactly the row that used to carry no id at all.
    """
    if not any(ids):
        return None
    return ",".join(vrs_id or "" for vrs_id in ids)


def validate_vrs_id_list(value: str | None, field_name: str = "vrs_id") -> str | None:
    """Validate a comma-joined `vrs_id` cell member by member, returning the canonical spelling.

    Each member is either a well-formed VRS **allele** id or empty. Alignment with `alts` is *not*
    checked here — a field validator cannot see a sibling field — so `ResolutionRow` checks the count
    itself.
    """
    ids = split_vrs_ids(value)
    for index, member in enumerate(ids):
        validate_vrs_allele_id(member, f"{field_name}[{index}]" if len(ids) > 1 else field_name)
    return join_vrs_ids(ids)


def validate_vrs_id(value: str | None, field_name: str = "vrs_id") -> str | None:
    """Validate an optional GA4GH VRS identifier of **any** identifiable type.

    Well-formedness only: `ga4gh:<TYPE>.<32-char digest>`. Deliberately lenient (see
    `VRS_ID_PATTERN`) so a validator rejects a *malformed* value rather than an
    unfamiliar-but-well-formed one. Whether a given **column** may hold a non-allele type is a
    separate question, and for the two `vrs_id` columns the answer is no — they use
    `validate_vrs_allele_id`.
    """
    if value is not None and not VRS_ID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a GA4GH VRS identifier like "
            f"ga4gh:VA.JGrSjQEcYOJ14vlkvm7sIyYSgHfpC5UG, got: {value!r}"
        )
    return value


def validate_vrs_allele_id(value: str | None, field_name: str = "vrs_id") -> str | None:
    """Well-formed **and** an allele id — the rule `ResolutionRow.vrs_id`/`FrequencyRow.vrs_id` obey.

    **Settling this is what RM78's severity question was gated on.** Both columns are described as
    *"GA4GH VRS allele id (`ga4gh:VA.…`) — one per ALT"*, and only the lenient format check ran — so a
    `ga4gh:SL.…`, a *sequence-location* id naming a place rather than an allele, loaded cleanly. It
    then reached `_verify_vrs_ids`, which recomputes with `derive_vrs_allele_id` (always a VA), found
    a difference, and reported a **mismatch**: *"recomputed and different, so corruption"*. That
    verdict is already an error in both modes, so this tightening makes no passing module fail — it
    replaces a confident wrong diagnosis with the true one, at load, naming the type it got.

    **Legal because it has no instantiation**, which is the test this repo applies to a tightening
    (the IUPAC probe is the precedent). Nothing mints a non-VA into either column — both minting paths
    call `derive_vrs_allele_id`, and gnomAD's own id is an allele id — and a probe across all sixteen
    reference examples found **844 ids, every one `ga4gh:VA.`, zero of the other four types**.

    `validate_vrs_id` keeps its documented lenience and its place. What was wrong was using a *format*
    check where a *column* rule was meant: a column that holds one kind of thing should say which.
    """
    validate_vrs_id(value, field_name)
    if value is not None and not value.startswith(VRS_ALLELE_PREFIX):
        kind = value.split(".", 1)[0].removeprefix("ga4gh:")
        raise ValueError(
            f"{field_name} must be a VRS allele id ({VRS_ALLELE_PREFIX}…), got a {kind} id: "
            f"{value!r}. This column names one allele per ALT and its value is recomputed with "
            f"derive_vrs_allele_id, so a {kind} id names something else and could never verify."
        )
    return value


def validate_caid(value: str | None, field_name: str = "caid") -> str | None:
    """Validate an optional ClinGen Allele Registry canonical allele id (`CA<digits>`)."""
    if value is not None and not CAID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a ClinGen canonical allele id like CA125138, got: {value!r}"
        )
    return value
