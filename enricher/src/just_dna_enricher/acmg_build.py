"""ACMG SF snapshot builder — the `[dev]` half of the `acmg_sf` check, and the reason it was needed.

`acmg.py` shipped the guarded scrape of NCBI's adaptation of ACMG Table 1 because, probed 2026-08-03,
that page was the only machine-reachable form of the list. That was true and it is no longer enough:
**NCBI serves v3.2 and ACMG published v3.3 in June 2025** (Miller et al.,
`10.1016/j.gim.2025.101454`), which the scrape cannot know. A list a year behind does not fail the
scrape's five guards — the page is not truncated, it is simply old — so the check answered
`acmg_sf=true but ABCD1 is not on ACMG SF v3.2` about a correctly authored row. That is the exact
failure mode `parse_acmg_page`'s guards exist to prevent, arriving by a route no guard could see.

**So the list becomes injected, like every other reference in this repo.** ACMG publishes v3.3 as a
supplementary **workbook** beside the statement, which is a better artifact than the page in every way
that matters: it is version-pinned behind a DOI rather than hand-maintained, it is content-hashable,
and it carries four columns the page does not — `Inheritance`, `Phenotype Category`, the SF release
that first listed the gene, and ACMG's own scope-of-reporting text. This module turns that workbook
into the small snapshot `acmg.load_acmg_snapshot` reads.

**Builder-only, so `openpyxl` is a `[dev]` extra** — the same split `clinvar_build`/`constraint_build`
make with `polars`, and for the reason CLAUDE.md records: a *runtime* pass may not depend on a `[dev]`
package. The snapshot is CSV and the pass reads it with the standard library, so `check-acmg --sf-list`
works on a plain `pip install just-dna-enricher`.

**Nothing is fetched.** The workbook is ACMG/Elsevier supplementary material and the author supplies
their own copy, which is the inject-only shape the charter asks for anyway (Principle 2) — a snapshot
is a *reference*, and references are injected here, not downloaded by a builder. `assets/` carries the
v3.3 workbook unmodified beside the v3.2 page it supersedes so the version gap is a test fixture rather
than a description, and `release.json` records the DOI and the `source_sha256` so a built snapshot says
where it came from.

**The workbook has its own malformations, and one of them is the same shape as the `<tr>` bug.** Row
105 of the v3.3 sheet is ACMG's disclaimer, and its ~1,200 characters of prose sit **in the Gene
column** — so the naive read reports 85 genes where there are 84, and `Disclaimer: This statement is
designed…` becomes a gene symbol that no authored row will ever match. Three cells carry embedded
newlines (`Cardiovascular\\nMetabolic`, and two multi-MIM cells), the `Inheritance` header and some of
its values carry trailing spaces, and the disease header is misspelled `Disease/Phentyope` — which is
why the headers are matched by prefix and resolved **by name to a column index**, never positionally.
"""

import csv
import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from just_dna_enricher.acmg import (
    MIN_GENES,
    SNAPSHOT_CSV,
    SNAPSHOT_RELEASE,
    AcmgSfError,
    AcmgSfList,
    SecondaryFinding,
    parse_sf_version,
)

try:  # the one guarded optional import (CLAUDE.md): openpyxl is builder-only ([dev] extra)
    import openpyxl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    openpyxl = None

logger = logging.getLogger(__name__)

#: Where ACMG published v3.3. Recorded so a stale-list message can name the file to download rather
#: than telling an author their module is wrong. Not fetched: it is a publisher CDN URL for one
#: version, and the next version will have a different one.
SF_V3_3_DOI = "10.1016/j.gim.2025.101454"
SF_V3_3_SUPPLEMENT_URL = (
    "https://ars.els-cdn.com/content/image/1-s2.0-S1098360025001017-mmc1.xlsx"
)

#: Each expected column, as a **prefix** of the sheet's header text, resolved to whatever index it is
#: found at. Prefixes rather than equality because ACMG misspells one of them (`Disease/Phentyope`)
#: and pads another (`Inheritance `); by name rather than by position because a reordered column must
#: move the reader, not silently shift every value one to the left.
_COLUMNS: dict[str, str] = {
    "gene": "Gene",
    "gene_mim": "Gene MIM",
    "disease": "Disease",
    "disease_mims": "Disorder MIM",
    "phenotype_category": "Phenotype Category",
    "inheritance": "Inheritance",
    "since_version": "SF List Version",
    "variants_to_report": "Variants to report",
}

#: A gene symbol, deliberately narrow. Its whole job is to separate the 84 symbols from the one cell
#: of disclaimer prose sharing their column, so the bound on length is the load-bearing part.
_SYMBOL_RE = re.compile(r"^[A-Z][A-Za-z0-9._\-]{0,19}$")

_SNAPSHOT_FIELDS = (
    "gene",
    "gene_id",
    "gene_mim",
    "disease",
    "disease_mims",
    "medgen_ids",
    "phenotype_category",
    "inheritance",
    "since_version",
    "variants_to_report",
)


def _text(value: Any) -> Optional[str]:
    """A cell → its text with every run of whitespace collapsed, or None if it is empty.

    Collapsing rather than stripping: three cells in the real sheet carry embedded newlines
    (`Cardiovascular\\nMetabolic`, `115310,\\n171300`), and a value that contains a line break is not a
    different value from the same value written on one line.
    """
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_acmg_workbook(path: Path) -> AcmgSfList:
    """ACMG's supplementary workbook → the list it publishes, or a refusal.

    The guards mirror `parse_acmg_page`'s, because they defend the same thing — a **short list**, which
    would make a correctly authored `acmg_sf=true` row look wrong:

    1. the sheet must declare an `ACMG (SF|Secondary Findings) vN.N` version, and if both the sheet name
       and its title cell declare one they must agree;
    2. every column in `_COLUMNS` must be findable by prefix, and each is then read by the index it was
       found at;
    3. a row whose Gene cell is not a gene symbol is only skipped when **every other cell in it is
       empty** — that is ACMG's trailing disclaimer, and anything else is a refusal rather than a guess;
    4. a gene symbol with no Gene MIM is a refusal for the same reason;
    5. at least `MIN_GENES` distinct genes must survive.
    """
    if openpyxl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise AcmgSfError(
            "reading an ACMG workbook needs openpyxl, which is a [dev] extra: install "
            "`just-dna-enricher[dev]`. The runtime check reads the built snapshot and needs nothing."
        )
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = workbook.worksheets[0]
    rows = [row for row in sheet.iter_rows(values_only=True)]
    if not rows:
        raise AcmgSfError(f"{path}: the first worksheet is empty")

    version = _workbook_version(sheet.title, rows, path)
    header_index, columns = _resolve_columns(rows, path)

    findings: list[SecondaryFinding] = []
    for number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        cells = {name: _text(row[index]) if index < len(row) else None for name, index in columns.items()}
        gene = cells["gene"]
        if gene is None:
            continue
        if not _SYMBOL_RE.match(gene):
            others = [value for name, value in cells.items() if name != "gene" and value]
            if others:
                raise AcmgSfError(
                    f"{path}: row {number} has {gene[:60]!r} in the Gene column and {len(others)} "
                    f"other populated cell(s) — that is a data row whose gene symbol cannot be read, "
                    f"not ACMG's trailing disclaimer, so refusing rather than dropping a gene"
                )
            logger.debug("row %d is trailing prose in the Gene column, skipped", number)
            continue
        if not cells["gene_mim"]:
            raise AcmgSfError(
                f"{path}: row {number} lists gene {gene} with no Gene MIM — the sheet's shape moved "
                f"and the columns can no longer be trusted"
            )
        findings.append(
            SecondaryFinding(
                gene=gene,
                # The workbook links nothing, so there is no NCBI Gene id to read. 0 rather than a
                # fabricated one: `gene_id` is provenance from the page, and inventing a value here
                # would make two snapshots of the same list disagree on a column neither verdict uses.
                gene_id=0,
                gene_mim=cells["gene_mim"],
                disease=cells["disease"],
                # Bare numbers here, unlike the page's `MIM 115310` prose — and several per cell
                # (`RPE65` is listed against `204100, 613794`), which is why it is a findall.
                disease_mims=tuple(re.findall(r"\d{5,6}", cells["disease_mims"] or "")),
                # MedGen concept ids live on NCBI's page, not in ACMG's workbook. Empty rather than
                # absent-and-therefore-guessed; nothing in a verdict reads them.
                medgen_ids=(),
                phenotype_category=cells["phenotype_category"],
                inheritance=cells["inheritance"],
                since_version=None if (cells["since_version"] or "").lower() == "none" else cells["since_version"],
                variants_to_report=cells["variants_to_report"],
            )
        )

    genes = {f.gene for f in findings}
    if len(genes) < MIN_GENES:
        raise AcmgSfError(
            f"{path}: parsed only {len(genes)} distinct genes from ACMG SF v{version}, below the "
            f"{MIN_GENES} floor — the workbook is truncated or is not the gene-list sheet"
        )
    logger.info(
        "ACMG SF v%s workbook: %d genes over %d gene-condition rows", version, len(genes), len(findings)
    )
    return AcmgSfList(
        version=version,
        findings=findings,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_url=str(path),
    )


def _workbook_version(sheet_title: str, rows: list[tuple], path: Path) -> str:
    """The version the sheet declares about itself, from the tab name and the title cell.

    Both carry it in the real file (`ACMG SF v3.3 Gene List`; `"The ACMG Secondary Findings v3.3
    list is provided here…"`). Either alone is accepted; **disagreement is a refusal**, because a tab
    renamed without its contents (or the reverse) is precisely the mix-up that would report the wrong
    version alongside the right genes.
    """
    from_title = parse_sf_version(sheet_title)
    prose = " ".join(str(cell) for row in rows[:3] for cell in row if isinstance(cell, str))
    from_prose = parse_sf_version(prose)
    if from_title and from_prose and from_title != from_prose:
        raise AcmgSfError(
            f"{path}: the sheet name declares ACMG SF v{from_title} and its title cell declares "
            f"v{from_prose} — refusing rather than reporting against a version that is not the genes"
        )
    version = from_title or from_prose
    if version is None:
        raise AcmgSfError(
            f"{path}: neither the sheet name nor its title rows declare an 'ACMG SF vN.N' version — a "
            f"list with no version cannot be reported against"
        )
    return version


def _resolve_columns(rows: list[tuple], path: Path) -> tuple[int, dict[str, int]]:
    """Find the header row, and map each `_COLUMNS` name to the index it actually occupies."""
    for index, row in enumerate(rows[:10]):
        labels = {position: _text(cell) or "" for position, cell in enumerate(row)}
        resolved: dict[str, int] = {}
        for name, prefix in _COLUMNS.items():
            matches = [position for position, label in labels.items() if label.startswith(prefix)]
            # `Gene` is a prefix of `Gene MIM`, so the shortest match wins by exactness: prefer a
            # label equal to the prefix, else the single remaining candidate.
            exact = [position for position in matches if labels[position] == prefix]
            if len(exact) == 1:
                resolved[name] = exact[0]
            elif len(matches) == 1:
                resolved[name] = matches[0]
        if len(resolved) == len(_COLUMNS) and len(set(resolved.values())) == len(_COLUMNS):
            return index, resolved
    raise AcmgSfError(
        f"{path}: no row in the first 10 carries all of {sorted(_COLUMNS.values())} as distinct "
        f"columns — the sheet was re-laid out, so it cannot be read"
    )


def build_acmg_snapshot(
    workbook: Path, out_dir: Path, *, source_url: Optional[str] = None, doi: Optional[str] = None
) -> AcmgSfList:
    """Workbook → `acmg_sf.csv` + `release.json` in `out_dir`, for `acmg.load_acmg_snapshot`.

    `release.json` carries the provenance that makes the snapshot citable rather than merely present:
    the declared `sf_version`, the `source_sha256` of the bytes it was built from, the publication DOI,
    and the counts. `source_sha256` is the point — a snapshot with no hash of its input is a claim
    about ACMG's list with nothing behind it, and this is the same pin `clinvar build` writes.
    """
    sf_list = parse_acmg_workbook(workbook)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / SNAPSHOT_CSV
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_SNAPSHOT_FIELDS)
        writer.writeheader()
        # Sheet order, never set order (P7): a snapshot rebuilt from the same workbook is byte-identical.
        for finding in sf_list.findings:
            record = asdict(finding)
            record["disease_mims"] = ",".join(finding.disease_mims)
            record["medgen_ids"] = ",".join(finding.medgen_ids)
            writer.writerow({field: record.get(field) or "" for field in _SNAPSHOT_FIELDS})

    release = {
        "sf_version": sf_list.version,
        "source_url": source_url or SF_V3_3_SUPPLEMENT_URL,
        "source_file": workbook.name,
        "source_sha256": "sha256:" + hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "doi": doi or SF_V3_3_DOI,
        "gene_count": len(sf_list.genes),
        "row_count": len(sf_list.findings),
        "built_at": sf_list.retrieved_at,
        "builder": "just_dna_enricher.acmg_build",
    }
    (out_dir / SNAPSHOT_RELEASE).write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "wrote ACMG SF v%s snapshot to %s (%d genes, %d rows)",
        sf_list.version, out_dir, release["gene_count"], release["row_count"],
    )
    return sf_list
