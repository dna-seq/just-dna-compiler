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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from just_dna_format.sources import SourceRow
from just_dna_format.vocab import VALID_DECLARED_USE

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
    license: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    notice: Optional[str] = None
    share_alike: Optional[bool] = None
    commercial_use: Optional[bool] = None
    redistribution: Optional[bool] = None

    def row(
        self,
        layer: str,
        *,
        declared_use: str,
        dataset: Optional[str] = None,
        license_text: Optional[str] = None,
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
            fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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


def check_declared_use(terms: SourceTerms, declared_use: str) -> Optional[str]:
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
    if declared_use not in VALID_DECLARED_USE:
        raise ValueError(
            f"declared_use must be one of {sorted(VALID_DECLARED_USE)}, got: {declared_use!r}"
        )
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


SOURCES_FIELDNAMES = [
    "source", "layer", "license", "license_url", "license_sha256", "attribution", "notice",
    "share_alike", "commercial_use", "declared_use", "dataset", "fetched_at",
]


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
