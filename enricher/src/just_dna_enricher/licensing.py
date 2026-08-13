"""Data-source terms, and the declared-use gate (0.5).

The enricher is the only tier that fetches, so it is the only tier that knows where a fact came from
and on what terms. This module owns both halves of that: the terms for each service it can reach, and
the refusal that happens at the moment of acquisition.

**Why the refusal lives here and not in the compiler.** Under a data-usage policy, the terms are
accepted when the data is *taken*. Refusing here means nothing is fetched; refusing at compile would
only mean nothing is written, after the copy already exists on disk. The compiler still has a gate,
but it is a different one — it enforces that whatever a module *carries* is accompanied by a
declaration, computed purely from the injected `sources.csv`.

**Why the constants sit beside the client that uses them, not in a shared registry.** The pair
(endpoint, terms) is one fact about one service; separating them is how they drift. `TERMS` here is
the small residue that cannot be read from the payload: a service that ships no licence file with its
data has to be described somewhere. Where a source *does* ship its terms — ClinPGx bundles a
`LICENSE.txt` inside every archive — the pass reads them out of the same bytes it took the data from
and overrides the constant, which makes the recorded licence provably contemporaneous with the
recorded data rather than a lookup that was true once.

That distinction is not theoretical. Both halves of the static table went stale inside a single
release: `api.pharmgkb.org` was retired on 2026-07-20, and CPIC's licence page moved to the ClinPGx
policy when the two merged. A recorded `license_sha256` turns the next such change into a finding.
"""

import csv
import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.layout import SOURCES_CSV, SidecarCollision, sidecar_write_path
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import VALID_DECLARED_USE, check_vocab

logger = logging.getLogger(__name__)


class LicenseRefusal(RuntimeError):
    """Raised when a declared use is incompatible with a source's terms.

    Fatal in **both** modes, unlike most enricher findings. The mode ladder grades how confident we
    are in a *finding*; this is not a finding about the data, it is a statement that the fetch is not
    permitted. `best_effort` means "resolve what you can", never "take what you may not".
    """


@dataclass(frozen=True)
class SourceTerms:
    """The terms a service publishes, as far as they can be established without the payload."""

    source: str
    license: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    notice: str | None = None
    share_alike: bool | None = None
    commercial_use: bool | None = None
    redistribution: bool | None = None

    def row(
        self,
        layer: str,
        *,
        declared_use: str,
        dataset: str | None = None,
        license_text: str | None = None,
    ) -> SourceRow:
        """A `SourceRow` for this source at `layer`.

        `license_text`, when the pass could read the terms out of the payload, is hashed into
        `license_sha256` — pinning the terms to the same moment as the data.
        """
        return SourceRow(
            source=self.source,
            layer=layer,
            license=self.license,
            license_url=self.license_url,
            license_sha256=(
                "sha256:" + hashlib.sha256(license_text.encode("utf-8")).hexdigest()
                if license_text is not None
                else None
            ),
            attribution=self.attribution,
            notice=self.notice,
            share_alike=self.share_alike,
            commercial_use=self.commercial_use,
            redistribution=self.redistribution,
            declared_use=declared_use,
            dataset=dataset,
            fetched_at=now_utc_iso(),
        )


# ── The terms, as read on 2026-08-02 ────────────────────────────────────────────────────────────
#
# All three pharmacogenomics sources are CC BY-SA 4.0 **plus** a separate contractual bar on sale, so
# `commercial_use=False` for each. Do not read a bare "CC BY-SA 4.0" line as permission to sell — the
# CC grant covers the content while the surrounding terms restrict the use, and PharmVar in particular
# states the licence and the restriction in adjacent sentences.
#
# **All five permit redistribution**, so `redistribution=True` throughout — CC BY-SA and CC0 both grant
# it explicitly, and Apache-2.0 does too. It is recorded rather than left null because null means "the
# terms could not be established", which is a different and weaker statement than "they allow it". The
# axis exists for the sources this workspace does NOT yet reach: OMIM and dbNSFP are academic-use-only,
# which bars passing the data on at all — something `commercial_use=False` alone understates, since
# CC BY-NC forbids sale while expressly allowing sharing.
CLINPGX_TERMS = SourceTerms(
    source="clinpgx",
    license="CC-BY-SA-4.0",
    license_url="https://www.clinpgx.org/page/dataUsagePolicy",
    attribution="ClinPGx (https://www.clinpgx.org/page/citingClinpgx)",
    notice="ShareAlike; ClinPGx data may not be sold for private or commercial use.",
    share_alike=True,
    commercial_use=False,
    redistribution=True,
)

# CPIC merged into ClinPGx, and `cpicpgx.org/license/` now 302-redirects to the ClinPGx data usage
# policy — so CPIC is NOT an unrestricted alternative to ClinPGx, it is the same terms.
CPIC_TERMS = SourceTerms(
    source="cpic",
    license="CC-BY-SA-4.0",
    license_url="https://www.clinpgx.org/page/dataUsagePolicy",
    attribution="CPIC (https://cpicpgx.org), part of ClinPGx",
    notice="ShareAlike; CPIC/ClinPGx data may not be sold for private or commercial use.",
    share_alike=True,
    commercial_use=False,
    redistribution=True,
)

# PharmVar terms-and-conditions §3: the database content is CC BY-SA 4.0, and in the preceding
# sentence, "you agree to only use the data for research purposes and not with any intent to offer
# all or any part of the data for sale as a commercial item". §3 also carries the diagnostic-use
# disclaimer, which rides along in `notice` because that is where a consumer will actually see it.
PHARMVAR_TERMS = SourceTerms(
    source="pharmvar",
    license="CC-BY-SA-4.0",
    license_url="https://www.pharmvar.org/terms-and-conditions",
    attribution="PharmVar (https://www.pharmvar.org)",
    notice=(
        "ShareAlike; research use only, not for sale as a commercial item; not intended for direct "
        "diagnostic use or medical decision-making."
    ),
    share_alike=True,
    commercial_use=False,
    redistribution=True,
)

# ClinGen's terms-of-use page states that all curated content is "available free of restriction under
# the CC0 1.0 Universal (CC0 1.0) Public Domain Dedication", and then *requests* — does not require —
# attribution with the date accessed. So attribution is recorded (it is the right thing to do and the
# column exists to carry it) while `share_alike` stays False: a request is not a licence condition,
# and recording it as one would overstate the obligation the module is under.
#
# Worth stating plainly because it is the exception in this file: ClinGen is the one annotation-layer
# source here that a module can be *sold* on. Every PGx upstream above forbids it.
CLINGEN_TERMS = SourceTerms(
    source="clingen",
    license="CC0-1.0",
    license_url="https://clinicalgenome.org/docs/terms-of-use/",
    attribution="ClinGen (https://clinicalgenome.org), accessed via the gene-curation list",
    notice="CC0 public-domain dedication; attribution requested but not required.",
    share_alike=False,
    commercial_use=True,
    redistribution=True,
)

# ClinVar is NCBI public-domain: US-government work, no copyright asserted over the aggregate. It is
# already consulted as a resolver link and for the `clin_sig` cross-check; a drafting provider *copies*
# rows out of it, which is the point at which a module must be able to say where they came from. The
# NCBI disclaimer asks for citation and warns the data is not for clinical diagnosis unaided — recorded
# in `notice` because the table exists to carry exactly that, not only to carry prohibitions.
CLINVAR_TERMS = SourceTerms(
    source="clinvar",
    license="public-domain",
    license_url="https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/",
    attribution="ClinVar, NCBI (https://www.ncbi.nlm.nih.gov/clinvar/)",
    notice=(
        "US-government work, no copyright asserted. NCBI asks that ClinVar be cited and states the "
        "records are submitter assertions, not a clinical diagnosis."
    ),
    share_alike=False,
    commercial_use=True,
    redistribution=True,
)

# Already in the chain and unrestricted — recorded so a module's licence picture is complete rather
# than only listing the sources that constrain it.
ENSEMBL_TERMS = SourceTerms(
    source="ensembl",
    license="Apache-2.0",
    license_url="https://www.ensembl.org/info/about/legal/disclaimer.html",
    attribution="Ensembl (https://www.ensembl.org)",
    share_alike=False,
    commercial_use=True,
    redistribution=True,
)


# gnomAD, read from `browser/about/policies/terms.md` in broadinstitute/gnomad-browser on 2026-08-03:
# "The primary data from the gnomAD exomes and genomes are available free of restrictions under the
# Creative Commons Zero Public Domain Dedication. This means that you can use it for any purpose
# without legally having to give attribution. However, we request that you actively acknowledge and
# give attribution to the gnomAD project". So the shape is ClinGen's: CC0, `share_alike=False`,
# attribution recorded because it is asked for and the column exists to carry it, not because it binds.
#
# Two things from the same page ride in `notice` rather than being dropped, because a consumer needs
# them and no flag expresses them: the no-reidentification undertaking every user of the data accepts,
# and the fact that **layered annotations carry their own terms** — SpliceAI in the browser is CC BY-NC
# 4.0. That second one is exactly RM23's territory, and it is the reason "gnomAD is CC0" must not be
# read as covering everything gnomAD serves.
GNOMAD_TERMS = SourceTerms(
    source="gnomad",
    license="CC0-1.0",
    license_url="https://gnomad.broadinstitute.org/policies",
    attribution="gnomAD, Broad Institute (https://gnomad.broadinstitute.org)",
    notice=(
        "CC0 public-domain dedication for the primary exome/genome data; attribution requested but "
        "not required. Users agree not to attempt to reidentify participants. Some layered "
        "annotations carry their own terms (SpliceAI is CC BY-NC 4.0, academic/non-commercial)."
    ),
    share_alike=False,
    commercial_use=True,
    redistribution=True,
)

#: Which **licensed source** each resolution **link** speaks for.
#:
#: `resolution.csv`'s `source` names the link that answered (`ensembl-rest`, `cache`, …) while
#: `sources.csv`'s names a licensed source (`ensembl`, `clinvar`, …). Two vocabularies under one name,
#: which is why `ResolutionRow.authority` exists and why this map lives **here**: the enricher is the
#: only tier permitted to hold a source convention (P2, tightened in 0.5), and `licensing.py` already
#: says in as many words that the same map in the compiler would be an un-injected reference.
#:
#: A link with **no entry** has no external authority to declare, and that is a real answer rather than
#: a gap: `authored` is the module's own bytes, `reversed` is the compiler rebuilding the table from
#: parquet, and `manual` is a human. Recording a licensed source for any of those would invent one.
RESOLUTION_AUTHORITY_BY_LINK: dict[str, str] = {
    "cache": "ensembl",          # the Ensembl snapshot — same data, offline
    "ensembl": "ensembl",
    "ensembl-rest": "ensembl",
    "ensembl-graphql": "ensembl",
    "clinvar": "clinvar",
    "gnomad": "gnomad",
}

#: Every source whose terms this tier can state, by the identifier that joins `sources.csv.source`.
TERMS_BY_SOURCE: dict[str, SourceTerms] = {
    terms.source: terms
    for terms in (
        CLINPGX_TERMS,
        CPIC_TERMS,
        PHARMVAR_TERMS,
        CLINGEN_TERMS,
        CLINVAR_TERMS,
        ENSEMBL_TERMS,
        GNOMAD_TERMS,
    )
}


def resolution_authority(link: str | None) -> str | None:
    """The licensed source a resolution link speaks for, or `None` when there is no external one."""
    return RESOLUTION_AUTHORITY_BY_LINK.get(link or "")


def record_source_terms(
    source_names: Iterable[str],
    layer: str,
    spec_dir: Path,
    *,
    error: type[Exception],
    declared_use: str = "unstated",
) -> list[SourceRow]:
    """Record the terms of every licensed source a pass consulted, at `layer`.

    **A pass that consults a source must write its `SourceRow`** — the rule `clingen.py` and then
    `pgx_draft.py` each shipped without. The compile gate and `manifest.sources` read `sources.csv` and
    nothing else, so a source that is only *used* is a source the module cannot account for. The three
    machine-fact passes (resolution, frequency, gene metrics) all skipped it, which is why
    `VALID_SOURCE_LAYERS` has reserved members nothing ever wrote.

    None of these layers can taint a module: `taints_commercial_use` requires the `annotation` layer,
    because a coordinate or an AC/AN is a fact the source *reports* rather than expression it *owns*. So
    what this records is **attribution** — which gnomAD, Ensembl and ClinVar all request and none of
    them enforces — and that is precisely the case the table exists to carry, not only prohibitions.
    `declared_use` defaults to `unstated` because no fact-layer source here forbids sale, so these
    passes never have to ask the author for a declaration.

    A name with no terms constant is skipped rather than guessed at: `TERMS_BY_SOURCE` is what this tier
    can state, and inventing a row for the rest would be worse than the compiler's honest warning that
    the terms are unrecorded. Existing rows are never clobbered (`merge_sources_file`), so a human's
    hand-written terms survive a re-run.
    """
    terms = [TERMS_BY_SOURCE[name] for name in sorted(set(source_names)) if name in TERMS_BY_SOURCE]
    if not terms:
        return []
    return merge_sources_file(
        [t.row(layer, declared_use=declared_use) for t in terms], spec_dir, error=error
    )


def check_declared_use(terms: SourceTerms, declared_use: str) -> str | None:
    """Decide whether a fetch may proceed. Returns a skip reason, or raises, or returns None to go.

    Three outcomes rather than two, and the middle one is the point:

    * **raise** — the source forbids sale and the caller declared `commercial`. A direct
      contradiction; refuse in both modes rather than take the data.
    * **skip (a reason string)** — either the caller declared nothing (`unstated`) and the source
      forbids sale, or the source's terms are *unknown*. Conservative by default: the tool must not
      assert a purpose on the user's behalf, and "we could not establish the terms" is not permission.
      Mirrors `--offline` making a pass a no-op with a warning rather than a failure.
    * **None** — proceed.
    """
    # Through the shared checker, so a `-`/`_` slip is canonicalized here exactly as it is in the cell
    # this gate later reads: a caller passing `non-commercial` must not get a different verdict from
    # the same string written into the file.
    declared_use = check_vocab(declared_use, VALID_DECLARED_USE, "declared_use") or declared_use
    if terms.commercial_use is None:
        return (
            f"{terms.source}: terms could not be established, so the data is not used. Unknown is "
            f"not a finding that it is forbidden — it is the absence of a finding either way."
        )
    if terms.commercial_use is True:
        return None
    if declared_use == "commercial":
        raise LicenseRefusal(
            f"{terms.source} is {terms.license} and its terms forbid offering the data for sale "
            f"({terms.license_url}). A commercial declaration cannot be reconciled with that, so "
            f"nothing was fetched. Use --use non-commercial if that describes your use."
        )
    if declared_use == "non_commercial":
        return None
    return (
        f"{terms.source} forbids sale and no use was declared, so it was skipped. Re-run with "
        f"--use non-commercial to record a declaration ({terms.license_url})."
    )


#: The `sources.csv` column order, **derived from the model** rather than hand-kept.
#:
#: It was a literal list, and it silently omitted `redistribution` — so every `sources.csv` this
#: workspace has ever written recorded that axis as *unknown* while the terms constants right above
#: state it as `True`, and `merge_sources_file` dropped the column again on every merge. RM27 is a gate
#: designed to read a column that never reached a single file. `SourceRow` has no compiler-stamped
#: fields (it is not an `AuthoredModel`), so every declared field is a column an author or a pass may
#: fill, and declaration order is the order this list already used — deriving it makes a future column
#: unloseable instead of merely present in the model.
SOURCES_FIELDNAMES = list(SourceRow.model_fields)


def _cell(value: object) -> str:
    """Render one `SourceRow` value to a CSV cell, tri-state intact.

    `None` → empty and `False` → `"false"` must stay distinguishable: the whole permission model
    turns on unknown not collapsing into forbidden, and an empty cell reloads as `None`.
    """
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def write_sources_csv(rows: list[SourceRow], path: Path) -> None:
    """Write `sources.csv` in a fixed column order (normalized, like every reverse writer)."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCES_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in SOURCES_FIELDNAMES})


def merge_sources_csv(rows: list[SourceRow], path: Path, existing: list[SourceRow]) -> list[SourceRow]:
    """Merge emitted rows into whatever is already recorded, never clobbering (as `enrich()` does).

    Sorted by (source, layer) so the emitted order is deterministic (Principle 7).
    """
    merged: dict[tuple[str, str], SourceRow] = {(r.source, r.layer): r for r in existing}
    for row in rows:
        merged.setdefault((row.source, row.layer), row)
    out = [merged[key] for key in sorted(merged)]
    write_sources_csv(out, path)
    return out


def sidecar_path(spec_dir: Path, name: str, *, error: type[Exception]) -> Path:
    """Where a machine-written sidecar lives for this module — the copy it has, else a fresh one.

    The enricher's single entry point into `just_dna_format.layout`, so a pass never joins a filename
    onto a spec directory itself. That matters twice over: the licence table has two accepted
    spellings (RM51), and any of them may sit under `derived/` (RM49). A pass keeping its own literal
    would read the split copy and write the flat one, leaving the module with two — which is the
    collision, arrived at by following the documented workflow rather than by misuse.

    `SidecarCollision` is re-raised as the caller's own error, so a pass still fails as itself rather
    than as a schema-tier `ValueError` nobody up the stack is catching.
    """
    try:
        return sidecar_write_path(spec_dir, name)
    except SidecarCollision as exc:
        raise error(str(exc)) from exc


def sources_path(spec_dir: Path, *, error: type[Exception]) -> Path:
    """Where this module's licence table lives — the file it already has, else the current spelling.

    Nine passes used to write `spec_dir / "sources.csv"` by hand; they all come through here now.
    """
    return sidecar_path(spec_dir, SOURCES_CSV, error=error)


def merge_sources_file(
    rows: list[SourceRow], spec_dir: Path, *, error: type[Exception]
) -> list[SourceRow]:
    """Read the module's licence table if it is there, merge `rows` in, and write it back.

    The read-merge-write every terms-emitting pass performs, in one place: a pass that consulted a
    source has to record it, and each of them was otherwise growing its own copy of these nine lines.
    An unparseable existing file raises rather than being overwritten — merging into a table that did
    not load would silently drop the rows already recorded. `error` is the caller's own exception
    type, so a failure still surfaces as that pass's error rather than as a licensing one.

    Takes the **spec directory**, not a path: resolving the filename here is what stops a caller
    naming a spelling the module does not use.
    """
    path = sources_path(spec_dir, error=error)
    existing: list[SourceRow] = []
    if path.exists():
        parsed, errors, _ = load_csv_rows(path, SourceRow, path.name)
        if errors:
            raise error(f"existing {path.name} is invalid: {errors[0]}")
        existing = parsed
    return merge_sources_csv(rows, path, existing)


def read_sources_file(spec_dir: Path) -> list[SourceRow]:
    """The module's licence rows as recorded, or `[]` when there are none that can be read.

    The gentle counterpart to the strict load inside `merge_sources_file`, for a *reader* whose only
    power is to let a check be skipped — `clinical.tautology_reason`, which asks whether the licence
    row says these annotation rows were drafted from the snapshot the check is about to read (RM4).

    Gentle deliberately, and in the same direction the rest of this codebase withholds: a table that
    could not be read has established nothing, so `[]` leaves every check running. A pass that
    *writes* must still fail loudly on an unreadable table — merging into one that did not load would
    drop rows already recorded — and `merge_sources_file` does.
    """
    try:
        path = sidecar_write_path(spec_dir, SOURCES_CSV)
    except SidecarCollision as exc:
        logger.warning("Cannot read this module's licence table (%s); treating it as unrecorded.", exc)
        return []
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    if errors:
        logger.warning("%s is invalid (%s); treating it as unrecorded.", path.name, errors[0])
        return []
    return rows
