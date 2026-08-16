"""ACMG secondary findings — the list `VariantRow.acmg_sf` was, until now, checked against nothing.

`acmg_sf` has been materialized into `weights.parquet` since 0.4 and validated by nobody: the compiler
cannot hold a gene list (that is the un-injected-reference mistake RM21 taught), and no pass in this
tier had one to compare against. This module closes that, and the interesting part is *why it took
until 0.5.1* — the answer is in `parse_acmg_page`, not in the check.

**There is still no data file, and the scrape is real.** Probed 2026-08-03: ClinGen's FTP publishes
gene-curation, region-curation, dosage and recurrent-CNV lists and **no secondary-findings list**;
ClinVar's own FTP tree carries no ACMG flag (`gene_condition_source_id` has 13,478 rows and zero
mentions of ACMG). The only machine-reachable form of SF v3.2 is NCBI's adaptation of ACMG's Table 1
at `/clinvar/docs/acmg/`, as HTML. So this is the "accept the guarded scrape" branch the roadmap left
open, taken with the guards that branch was made conditional on.

**The guards are not ceremony — the naive parse is wrong on the real page.** Splitting the table on
`<tr>` yields 78 of the 81 genes, silently. The page is hand-maintained HTML and it shows: two rows
open with a bare `<td>` after the previous `</tr>` with no `<tr>` of their own, four rows leave a
`<td>` unclosed and carry a stray trailing `</td>`, and the gene cell links through **three** different
URL shapes (`/gtr/genes/324`, `/gtr/genes/4089/`, `/gene/3949`). The three genes a `<tr>` split drops
are `TP53`, `COL3A1` and `TPM1` — which is the failure mode stated exactly: a short list makes a
correctly authored `acmg_sf=true` row look wrong, and it would have started with the single most
recognizable secondary-findings gene there is. The parse therefore works in **cells**, not rows
(`<td>` count must divide exactly by the header's column count), and refuses rather than returning a
short list.

**This pass records no `SourceRow`**, which is the deliberate exception to the standing rule that a
pass consulting a source must write one. That rule is about a module *carrying* a source's data:
`sources.csv` exists so a module can account for what is in it. Nothing here lands in the module —
`acmg_sf` was authored by a human before this ran, exactly as a gene symbol is, and this asks the
registry whether that authored value is still right. It is `check_identifiers`' shape (HGNC and OLS4
also go unrecorded), not `clingen`'s.

**Gene-level, and the column says so.** ACMG's table is keyed on gene *and* condition — 94 gene-disease
pairs over 81 genes — and reporting is scoped to P/LP variants for the named condition. `acmg_sf` is
documented as "True when the **gene** is on the ACMG secondary-findings list", so that is what is
compared; the conditions are parsed and kept on `SecondaryFinding` so a caller can say which entry
matched, but they are not part of the verdict. Reading the column as per-variant reportability would
make the format decide disclosure policy, which it explicitly does not.

**And the page turned out to be a version behind, which no guard above can see.** ACMG published
**SF v3.3** in June 2025 (84 genes over 100 gene-condition rows, adding `ABCD1`, `CYP27A1` and `PLN`);
NCBI still serves its adaptation of **v3.2** (81/94). The scrape's five guards all pass — the page is
neither truncated nor re-laid-out, it is simply old — so the check reported `acmg_sf=true but ABCD1 is
not on ACMG SF v3.2` about a row that is right. That is the same *short list* failure the guards were
built for, and this is the fix, in two halves:

* the list can now be **injected** — `acmg_build` turns ACMG's supplementary workbook into a snapshot
  and `load_acmg_snapshot` reads it with the standard library, which also makes the check the first one
  here that works `--offline`; and
* the scrape path carries a **staleness tripwire**, `KNOWN_LATEST_SF_VERSION`. When the list actually
  read is older than a version this package knows was published, every disagreement is demoted to
  `unverifiable` and no longer refuses under `strict`. A mismatch against a superseded list is a
  question, not an answer, and answering it anyway is worse than saying nothing (the house tri-state
  rule: unknown withholds — it never reports and never negates).

One constant is deliberately hand-kept, and its failure mode is why that is acceptable: a *version
string* is not the transcribed gene list this module exists to avoid. When ACMG ships v3.4 the constant
says 3.3 and the tripwire under-warns — i.e. degrades to the behaviour of the release before this one —
whereas a hand-kept gene list would make specific, confident, wrong claims about specific genes.
"""

import csv
import html
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_spec_variants
from just_dna_format.manifest import VerificationRecord
from just_dna_format.normalize import now_utc_iso
from just_dna_format.spec import VariantRow

from just_dna_enricher.verification import examples, ran, skipped

logger = logging.getLogger(__name__)

DEFAULT_ACMG_URL = "https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/"

#: The newest SF release this package knows exists. **Not** a gene list — one string, whose only job is
#: to stop a scrape of a superseded page from being silently authoritative. See the module docstring for
#: why the stale-constant risk is acceptable here and would not be for the list itself.
KNOWN_LATEST_SF_VERSION = "3.3"

#: The snapshot layout, owned by the **reader** rather than the builder: `load_acmg_snapshot` is the
#: contract a snapshot has to satisfy, and `acmg_build` imports these to conform. The other direction
#: would make the runtime module import the `[dev]` builder to learn its own file names.
SNAPSHOT_CSV = "acmg_sf.csv"
SNAPSHOT_RELEASE = "release.json"

#: The four column labels the table has carried since NCBI adapted it. A change here means the page
#: was re-laid-out and every offset below is suspect, so it is a refusal rather than a best guess.
EXPECTED_HEADERS = ("Disease name and MIM number", "MedGen", "Gene via GTR", "Variations that may")

#: A floor, not the real count — the real count is whatever ACMG publishes next and hard-coding it
#: would be the hand-transcribed list this module exists to avoid. It catches the cheap disasters: a
#: JavaScript shell, a truncated response, an error page that happens to contain a table.
MIN_GENES = 50

# Both spellings the publishers use: NCBI's page says "ACMG SF v3.2", ACMG's own workbook says "ACMG
# Secondary Findings v3.3" in its title cell and "ACMG SF v3.3" on the tab.
_VERSION_RE = re.compile(r"ACMG\s+(?:SF|Secondary\s+Findings)\s+v(\d+(?:\.\d+)*)")
# Three link shapes, all seen on the live page: /gtr/genes/324, /gtr/genes/4089/, /gene/3949.
_GENE_LINK_RE = re.compile(r'href="/(?:gtr/)?genes?/(\d+)/?"\s*>\s*([A-Za-z0-9_.\-]+)\s*</a>')
_MIM_RE = re.compile(r"MIM\s+(\d+)")
# Read off the cell *text* (`MedGen C1861848, C0031511`), not the href: the multi-concept cells link
# to a MedGen search rather than to a concept page, so the href carries a query and not an id.
_MEDGEN_ID_RE = re.compile(r"\b(C\d{5,})\b")
_TAG_RE = re.compile(r"<[^>]+>")


class AcmgSfError(RuntimeError):
    """An ACMG SF fetch or parse failed in a way the caller must see rather than work around."""


class AcmgListUnavailable(AcmgSfError):
    """No usable list was obtained, so the check could not be put at all (RM72).

    A subclass rather than a second exception, so every existing `except AcmgSfError` still catches
    it. It exists because this module has **two** ways of raising and a caller that attests must tell
    them apart: the list could not be read, or the module disagrees with a list that was read
    perfectly well (the `strict` refusal). Recording the second as a skip would say the question was
    never put, on the one run where it was put and answered badly — the answered-absence-versus-
    unasked-question collapse this tier draws everywhere else.

    `skip` carries the `VALID_VERIFICATION_SKIPS` member, decided where the failure happens rather
    than sniffed from the message: `unreachable` when the source was asked and never answered, and
    `no_reference` when something was there and no list could be read out of it.
    """

    def __init__(self, message: str, *, skip: str) -> None:
        super().__init__(message)
        self.skip = skip


@dataclass(frozen=True)
class SecondaryFinding:
    """One row of ACMG's Table 1: a gene, and the condition it is reportable for.

    `disease_mims` and `medgen_ids` are tuples because the real page puts **several** of each in one
    cell — `SDHB` is listed for "Hereditary paraganglioma-pheochromocytoma syndrome (MIM 115310,
    MIM 171300)" against `MedGen C1861848, C0031511`, and the MedGen cell then links to a *search*
    (`/medgen/?term=…+OR+…`) rather than to a concept. Taking the first of each would have been a
    silent truncation of the same family as the `<tr>` split.
    """

    gene: str
    gene_id: int
    gene_mim: str | None = None
    disease: str | None = None
    disease_mims: tuple[str, ...] = ()
    medgen_ids: tuple[str, ...] = ()

    # ── workbook-only columns (v3.3 supplement; blank when the list came from the page) ──
    # Carried because they are published facts about the entry and cost nothing to keep, and *not*
    # consulted by any verdict. `variants_to_report` in particular is ACMG's scope-of-reporting text
    # ("All P and LP", "p.C282Y homozygotes only") — reporting policy, which the roadmap files as
    # explicitly outside format scope. It is recorded so an author can read it, never applied.
    phenotype_category: str | None = None
    inheritance: str | None = None
    since_version: str | None = None
    variants_to_report: str | None = None


def parse_sf_version(text: str) -> str | None:
    """`ACMG SF v3.3` / `ACMG Secondary Findings v3.3` in `text` → `"3.3"`, else None."""
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _version_tuple(version: str) -> tuple[int, ...]:
    """`"3.3"` → `(3, 3)`, for ordering the releases ACMG has actually published (1, 2, 3, 3.1–3.3)."""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


@dataclass
class AcmgSfList:
    """The parsed list, with the version it declares about itself."""

    version: str
    findings: list[SecondaryFinding]
    retrieved_at: str
    source_url: str = DEFAULT_ACMG_URL

    @property
    def genes(self) -> frozenset[str]:
        return frozenset(f.gene for f in self.findings)

    def entries_for(self, gene: str) -> list[SecondaryFinding]:
        """Every condition this gene is listed for, in page order (P7: never set order)."""
        return [f for f in self.findings if f.gene == gene]

    @property
    def dataset(self) -> str:
        """The label a caller reports this check against, e.g. `acmg_sf_v3.2`."""
        return f"acmg_sf_v{self.version}"

    @property
    def superseded_by(self) -> str | None:
        """The newer SF version this package knows about, or None when this list is the newest known.

        Drives the demotion of every disagreement to `unverifiable`: a list that is a release behind
        cannot answer whether an authored flag is right, only whether it matches an old answer.
        """
        if _version_tuple(self.version) < _version_tuple(KNOWN_LATEST_SF_VERSION):
            return KNOWN_LATEST_SF_VERSION
        return None


@dataclass(frozen=True)
class AcmgVerdict:
    """One `variants.csv` row's answer, over the tri-state the authored column actually has.

    * `agree` — the authored value matches the list, either way round. Silent.
    * `not_listed` — authored True, gene is **not** listed. A finding.
    * `denied` — authored False, gene **is** listed. A finding, and the message names the entry.
    * `unverifiable` — a disagreement (either of the two above) against a list this package knows is
      **superseded**. A warning, never a `strict` refusal: ACMG SF v3.3 added three genes NCBI's v3.2
      page does not carry, so `not_listed` against v3.2 is exactly as likely to be the *list* being old
      as the module being wrong. Reporting it as a defect made the check confidently wrong about
      correctly authored rows, which is worse than not checking.
    * `unstated` — blank, gene is listed. A note, never a finding: blank means "not stated", and
      turning that into a defect is exactly the `None`-means-`False` collapse this codebase refuses.
    * `blank` — blank, gene is not listed. Nothing was asserted and nothing contradicts it.
    * `unchecked` — the row names no gene, or the list could not be reached. The question was never
      asked, which is not the same as being answered "no".
    """

    row: int
    gene: str | None
    authored: bool | None
    verdict: str
    message: str = ""


@dataclass
class AcmgReport:
    version: str | None
    verdicts: list[AcmgVerdict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def mismatches(self) -> list[AcmgVerdict]:
        """The verdicts that are defects — what `strict` refuses on."""
        return [v for v in self.verdicts if v.verdict in {"not_listed", "denied"}]

    @property
    def unverifiable(self) -> list[AcmgVerdict]:
        """Disagreements against a superseded list — reported, never refused. See `AcmgVerdict`."""
        return [v for v in self.verdicts if v.verdict == "unverifiable"]

    @property
    def notes(self) -> list[AcmgVerdict]:
        """Authoring aids, deliberately outside `mismatches`."""
        return [v for v in self.verdicts if v.verdict == "unstated"]

    @property
    def checked(self) -> int:
        """Rows the question could actually be asked about — never the row count."""
        return sum(1 for v in self.verdicts if v.verdict != "unchecked")

    @property
    def clean(self) -> bool:
        return not self.mismatches

    @staticmethod
    def by_gene(verdicts: list["AcmgVerdict"]) -> list[tuple[str, list[int], str]]:
        """`[(gene, [row numbers], message)]` — the shape a human should be shown.

        Every verdict here is about a *gene*, so a per-row list repeats one sentence once per row: the
        HFE reference example is 13 variants in one gene and printed the same 220-character note 13
        times. That is the aggregation rule this codebase already learned from CPIC (~600 identical
        lines for CYP2C19 buried every other finding). The per-row verdicts stay on the report for a
        caller that wants them; the grouping is what a report prints. First-occurrence order, never
        set order (P7).
        """
        grouped: dict[str, tuple[list[int], str]] = {}
        for verdict in verdicts:
            gene = verdict.gene or "(no gene)"
            if gene not in grouped:
                grouped[gene] = ([], verdict.message)
            grouped[gene][0].append(verdict.row)
        return [(gene, rows, message) for gene, (rows, message) in grouped.items()]


def _strip(fragment: str) -> str:
    """Cell markup → its text, whitespace-collapsed."""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", fragment))).strip()


def parse_acmg_page(text: str, *, source_url: str = DEFAULT_ACMG_URL) -> AcmgSfList:
    """The NCBI ACMG page → the list it publishes, or a refusal.

    Five guards, each of which is a way the page has actually been observed to fail or could fail
    into a *short list* rather than into an error — the outcome that would make this check worse than
    no check at all:

    1. the version string must be present (it is also the `dataset` label);
    2. the table must carry the four headers `EXPECTED_HEADERS` names;
    3. the `<td>` count must divide exactly by four — the page's rows are not reliably delimited, so
       the cells are the only trustworthy unit and a remainder means the shape moved;
    4. every four-cell group must yield exactly one gene link (zero would drop a gene silently, two
       would mean the cell boundaries slipped);
    5. at least `MIN_GENES` distinct genes must survive.
    """
    version_match = _VERSION_RE.search(text)
    if version_match is None:
        raise AcmgListUnavailable(
            f"{source_url} declares no 'ACMG SF vN.N' version — the page changed, and a list with no "
            "version cannot be reported against",
            skip="no_reference",
        )
    version = version_match.group(1)

    table = _select_table(text, source_url)
    cells = re.split(r"<td[^>]*>", table)[1:]
    width = len(EXPECTED_HEADERS)
    if not cells or len(cells) % width:
        raise AcmgListUnavailable(
            f"{source_url}: the ACMG table has {len(cells)} cells, which is not a multiple of "
            f"{width} — the column layout changed, so the list cannot be read positionally",
            skip="no_reference",
        )

    findings: list[SecondaryFinding] = []
    for index in range(0, len(cells), width):
        disease_cell, medgen_cell, gene_cell, _clinvar_cell = cells[index : index + width]
        links = _GENE_LINK_RE.findall(gene_cell)
        if len(links) != 1:
            raise AcmgListUnavailable(
                f"{source_url}: row {index // width + 1} has {len(links)} gene links in its gene "
                f"cell, expected exactly 1 — refusing rather than returning a list short by a gene "
                f"(cell: {_strip(gene_cell)[:120]!r})",
                skip="no_reference",
            )
        gene_id, symbol = links[0]
        gene_mim = _MIM_RE.search(_strip(gene_cell))
        disease_text = _strip(disease_cell)
        findings.append(
            SecondaryFinding(
                gene=symbol,
                gene_id=int(gene_id),
                gene_mim=gene_mim.group(1) if gene_mim else None,
                # MIMs are stripped from the *text*, not the markup: they arrive as `<a>MIM 115310</a>`
                # inside the parentheses, so removing them before tag-stripping matches nothing.
                disease=re.sub(r"\s*\(\s*(?:MIM \d+[,\s]*)+\)", "", disease_text).strip() or None,
                disease_mims=tuple(_MIM_RE.findall(disease_text)),
                medgen_ids=tuple(_MEDGEN_ID_RE.findall(_strip(medgen_cell))),
            )
        )

    genes = {f.gene for f in findings}
    if len(genes) < MIN_GENES:
        raise AcmgListUnavailable(
            f"{source_url}: parsed only {len(genes)} distinct genes from ACMG SF v{version}, below "
            f"the {MIN_GENES} floor — the response is truncated or is not the list page",
            skip="no_reference",
        )
    logger.info("ACMG SF v%s: %d genes over %d gene-condition rows", version, len(genes), len(findings))
    return AcmgSfList(
        version=version,
        findings=findings,
        retrieved_at=now_utc_iso(),
        source_url=source_url,
    )


def _select_table(text: str, source_url: str) -> str:
    """The one `<table>` carrying all four expected headers.

    The page has exactly one today, but selecting by header rather than by position means a future
    navigation or footer table cannot silently become "the list"."""
    for match in re.finditer(r"<table[^>]*>(.*?)</table>", text, re.DOTALL):
        body = match.group(1)
        header_end = body.find("</tr>")
        header = body[: header_end if header_end != -1 else len(body)]
        if all(label in header for label in EXPECTED_HEADERS):
            return body[header_end + len("</tr>") :] if header_end != -1 else body
    raise AcmgListUnavailable(
        f"{source_url}: no table carries the headers {EXPECTED_HEADERS} — the page was re-laid out",
        skip="no_reference",
    )


def fetch_acmg_page(url: str = DEFAULT_ACMG_URL, *, timeout: float = 60.0) -> str:
    """Download the SF page (~75 KB of HTML — one GET, no pacing needed)."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AcmgListUnavailable(
            f"could not fetch the ACMG secondary-findings page from {url}: {exc}",
            skip="unreachable",
        ) from exc
    return response.text


def check_acmg_sf(variants: list[VariantRow], sf_list: AcmgSfList) -> AcmgReport:
    """Compare each row's authored `acmg_sf` against the fetched list. Reports, never repairs."""
    listed = sf_list.genes
    verdicts: list[AcmgVerdict] = []
    for index, variant in enumerate(variants, start=1):
        gene = (variant.gene or "").strip()
        if not gene:
            verdicts.append(
                AcmgVerdict(index, None, variant.acmg_sf, "unchecked", "row names no gene")
            )
            continue
        on_list = gene in listed
        if variant.acmg_sf is None:
            if on_list:
                verdicts.append(
                    AcmgVerdict(
                        index, gene, None, "unstated",
                        f"{gene} is on ACMG SF v{sf_list.version} ({_conditions(sf_list, gene)}) "
                        f"and acmg_sf is blank — blank means 'not stated', which is legitimate; set "
                        f"it to true if the module means to carry the flag",
                    )
                )
            else:
                verdicts.append(AcmgVerdict(index, gene, None, "blank"))
            continue
        if variant.acmg_sf and not on_list:
            verdicts.append(
                _disagreement(
                    sf_list, index, gene, True, "not_listed",
                    f"acmg_sf=true but {gene} is not on ACMG SF v{sf_list.version} "
                    f"({len(listed)} genes)",
                )
            )
        elif not variant.acmg_sf and on_list:
            verdicts.append(
                _disagreement(
                    sf_list, index, gene, False, "denied",
                    f"acmg_sf=false but {gene} is on ACMG SF v{sf_list.version} "
                    f"({_conditions(sf_list, gene)}); the column is a gene-level list-membership "
                    f"fact, so leave it blank rather than false if this row is about a variant that "
                    f"is not itself a reportable secondary finding",
                )
            )
        else:
            verdicts.append(AcmgVerdict(index, gene, variant.acmg_sf, "agree"))
    return AcmgReport(version=sf_list.version, verdicts=verdicts)


def _disagreement(
    sf_list: AcmgSfList, index: int, gene: str, authored: bool, verdict: str, message: str
) -> AcmgVerdict:
    """A disagreement, demoted to `unverifiable` when the list read is a superseded release.

    Both directions are demoted, not just `not_listed`. `not_listed` is the observed case (v3.3 added
    `ABCD1`, `CYP27A1`, `PLN`, so a v3.3-authored module trips it against v3.2), but ACMG has removed
    entries before and the same argument applies in reverse: a `denied` verdict against a stale list
    could equally be the list still carrying a gene since dropped. Neither can be settled by the list
    in hand, so neither is asserted.
    """
    newer = sf_list.superseded_by
    if newer is None:
        return AcmgVerdict(index, gene, authored, verdict, message)
    return AcmgVerdict(
        index, gene, authored, "unverifiable",
        f"{message} — but the list read is v{sf_list.version} and ACMG SF v{newer} is published, so "
        f"this disagreement may be the list rather than the module. Build a snapshot from ACMG's "
        f"supplementary workbook and pass it with --sf-list to get an answer",
    )


def _conditions(sf_list: AcmgSfList, gene: str) -> str:
    names = [entry.disease for entry in sf_list.entries_for(gene) if entry.disease]
    return "; ".join(names) if names else "no condition named"


def load_acmg_snapshot(snapshot_dir: Path) -> AcmgSfList:
    """An `acmg build` snapshot directory → the list, read with the standard library only.

    Deliberately `csv` and `json` rather than the workbook reader: this is the **runtime** half, and a
    runtime pass may not depend on a `[dev]` package (the rule `clinpgx.py` learned by reading its own
    snapshot with polars). `openpyxl` stays in `acmg_build`, where it is a builder dependency.

    The `release.json` version is authoritative and must agree with nothing else — the CSV carries no
    version column, precisely so the two cannot drift.
    """
    release_path = snapshot_dir / SNAPSHOT_RELEASE
    csv_path = snapshot_dir / SNAPSHOT_CSV
    if not release_path.exists() or not csv_path.exists():
        raise AcmgListUnavailable(
            f"{snapshot_dir} is not an ACMG SF snapshot ({SNAPSHOT_RELEASE} + {SNAPSHOT_CSV} "
            f"expected) — build one with `just-dna-enricher acmg build <workbook.xlsx> <dir>`",
            skip="no_reference",
        )
    release = json.loads(release_path.read_text(encoding="utf-8"))
    version = release.get("sf_version")
    if not version:
        raise AcmgListUnavailable(
            f"{release_path} records no sf_version — the snapshot cannot be reported against",
            skip="no_reference",
        )

    findings: list[SecondaryFinding] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            gene = (row.get("gene") or "").strip()
            if not gene:
                continue
            findings.append(
                SecondaryFinding(
                    gene=gene,
                    gene_id=int(row["gene_id"]) if (row.get("gene_id") or "").strip().isdigit() else 0,
                    gene_mim=(row.get("gene_mim") or "").strip() or None,
                    disease=(row.get("disease") or "").strip() or None,
                    disease_mims=tuple(p for p in (row.get("disease_mims") or "").split(",") if p),
                    medgen_ids=tuple(p for p in (row.get("medgen_ids") or "").split(",") if p),
                    phenotype_category=(row.get("phenotype_category") or "").strip() or None,
                    inheritance=(row.get("inheritance") or "").strip() or None,
                    since_version=(row.get("since_version") or "").strip() or None,
                    variants_to_report=(row.get("variants_to_report") or "").strip() or None,
                )
            )
    if len({f.gene for f in findings}) < MIN_GENES:
        raise AcmgListUnavailable(
            f"{csv_path}: {len({f.gene for f in findings})} distinct genes, below the {MIN_GENES} "
            f"floor — the snapshot is truncated",
            skip="no_reference",
        )
    logger.info(
        "ACMG SF v%s snapshot: %d genes over %d rows (source %s)",
        version, len({f.gene for f in findings}), len(findings), release.get("source_sha256", "?"),
    )
    return AcmgSfList(
        version=str(version),
        findings=findings,
        retrieved_at=release.get("built_at", ""),
        source_url=release.get("source_url", str(snapshot_dir)),
    )


def _resolve_variants(
    variants: list[VariantRow] | None, spec_dir: Path | None
) -> list[VariantRow]:
    """Exactly one of `variants` / `spec_dir`, resolved to rows (RM41).

    Refuses both and refuses neither, rather than picking: a caller that passed both has two answers in
    mind and only one of them is right, and silently preferring either is the kind of guess this tier
    does not make anywhere else.
    """
    if (variants is None) == (spec_dir is None):
        raise AcmgSfError(
            "pass exactly one of variants= (rows you already hold) or spec_dir= (a module spec "
            "directory, loaded with the module\'s declared genome_build)"
        )
    if variants is not None:
        return variants
    loaded, errors, _ = load_spec_variants(Path(spec_dir))
    if errors:
        raise AcmgSfError(f"variants.csv is invalid: {errors[0]}")
    return loaded


def verify_acmg_sf(
    variants: list[VariantRow] | None = None,
    *,
    spec_dir: Path | None = None,
    mode: str = "best_effort",
    offline: bool = False,
    url: str = DEFAULT_ACMG_URL,
    page_text: str | None = None,
    snapshot_dir: Path | None = None,
) -> AcmgReport:
    """Read the list — injected snapshot first, then the live page — and check `variants` against it.

    **Pass either `variants` or `spec_dir` (RM41).** The row-taking form stays, because it is the right
    thing for an in-process caller that already holds the rows; `spec_dir=` matches the shape every
    other pass in this tier has, and spares a caller re-deriving the load — which is not
    `csv.DictReader` plus `Model(**row)` (see `compiler.load_spec_variants`).

    An injected `snapshot_dir` wins over the network unconditionally, which is the whole point: it is
    both the newer list and the one that works `--offline`. With no snapshot, `offline` reports nothing
    checked rather than nothing found — the same `unchecked` ≠ `absent` distinction every other pass in
    this tier draws.

    `strict` escalates a mismatch to a refusal; list membership is a published fact, not a clinical
    judgement, so unlike the `clin_sig` cross-check there is no reason to hold this one at a warning.
    It does **not** escalate an `unverifiable` — see `_disagreement`.
    """
    variants = _resolve_variants(variants, spec_dir)
    if snapshot_dir is not None:
        sf_list = load_acmg_snapshot(snapshot_dir)
    elif offline and page_text is None:
        report = AcmgReport(
            version=None,
            verdicts=[
                AcmgVerdict(index, (v.gene or None), v.acmg_sf, "unchecked", "offline")
                for index, v in enumerate(variants, start=1)
            ],
            warnings=[
                "--offline with no --sf-list: acmg_sf went unchecked. Build a snapshot from ACMG's "
                "supplementary workbook to check it without the network"
            ],
        )
        # Not logged. `report.warnings` IS the return value and every caller prints it, so logging it
        # here too emitted the same sentence twice under the default root handler — the mistake the
        # comment below `check_acmg_sf` already names for findings, which applies equally to warnings.
        return report
    else:
        sf_list = parse_acmg_page(
            page_text if page_text is not None else fetch_acmg_page(url), source_url=url
        )

    report = check_acmg_sf(variants, sf_list)
    newer = sf_list.superseded_by
    if newer is not None:
        report.warnings.append(
            f"the list read is ACMG SF v{sf_list.version} ({sf_list.source_url}) but v{newer} is "
            f"published — {len(report.unverifiable)} disagreement(s) could not be settled against it"
        )
    # Findings are the return value, not log output — the tier's convention is that a caller decides
    # how to present them and `logger` carries only what went wrong operationally. Logging them here
    # too would print every mismatch twice under the default root handler.
    logger.info(
        "acmg_sf checked against v%s: %d row(s), %d mismatch(es)",
        sf_list.version, report.checked, len(report.mismatches),
    )
    if mode == "strict" and report.mismatches:
        grouped = AcmgReport.by_gene(report.mismatches)
        # Plain `AcmgSfError`, deliberately, and `AcmgListUnavailable`'s docstring is why: the list was
        # read and the question was answered, so a caller attesting off this exception must not record
        # a skip. Nothing is attested on this path at all — the tier's rule for a `strict` refusal.
        raise AcmgSfError(
            f"strict acmg_sf check: {len(report.mismatches)} row(s) across {len(grouped)} gene(s) "
            f"disagree with ACMG SF v{sf_list.version}: "
            + "; ".join(f"{gene} ({len(rows)} row(s)): {message}" for gene, rows, message in grouped)
        )
    return report


# ── the attestation (RM72) ──────────────────────────────────────────────────────────────────────


def verification_record(report: AcmgReport) -> VerificationRecord:
    """This pass's one check, as a record `verification.json` can carry (RM72).

    **`subjects` is `report.checked`** — the rows the question could actually be asked about, which
    already excludes a row naming no gene and every row of a run that reached no list. Counting all
    the verdicts would publish a comparison for rows nobody compared, which is the shape the reference
    -allele pass fell into on an unbuilt assembly.

    **`findings` is `mismatches` alone**, and the `detail` sentence is what keeps that honest. A
    disagreement against a *superseded* list is demoted to `unverifiable` by `_disagreement` — every
    one of them, in both directions — so a run against NCBI's v3.2 page can hold ten disagreements and
    still have an empty `mismatches`. Recording `findings=0` with no further word would read as a
    clean bill, so the count of unsettled disagreements travels in `detail` and `release` names the
    list that could not settle them. `unstated` notes are authoring aids and are named there too;
    they are deliberately not findings, because blank means "not stated" and turning that into a
    defect is the `None`-means-`False` collapse this codebase refuses.

    The offline-with-no-list return is a **skip**, not `ran(0, 0)`: `verify_acmg_sf` is the only path
    that can produce a report with no version at all, and it produces one precisely when no list was
    consulted.
    """
    if report.version is None:
        return skipped(
            "acmg_secondary_findings", "offline",
            detail=(
                report.warnings[0] if report.warnings
                else "no list was consulted, so no acmg_sf cell was compared against one"
            ),
            source="acmg",
        )
    if not report.checked:
        return skipped(
            "acmg_secondary_findings", "nothing_to_check",
            # The version rides in the sentence rather than in `release`: that field belongs to a
            # comparison and this record is the statement that none was made. `skipped()` takes no
            # `release` for the same reason.
            detail=(
                f"none of {len(report.verdicts)} row(s) names a gene, so there was nothing to look "
                f"up in ACMG SF v{report.version}"
            ),
            source="acmg",
        )
    parts = []
    if report.mismatches:
        parts.append(
            f"{len(report.mismatches)} row(s) disagree with ACMG SF v{report.version}: "
            + examples([gene for gene, _rows, _message in AcmgReport.by_gene(report.mismatches)])
        )
    if report.unverifiable:
        parts.append(
            f"{len(report.unverifiable)} disagreement(s) could not be settled, because the list read "
            f"is v{report.version} and a newer one is published — they are outside the finding count "
            f"rather than absent from it"
        )
    if report.notes:
        parts.append(
            f"{len(report.notes)} row(s) leave acmg_sf blank for a listed gene, which is legitimate "
            f"and is a note rather than a finding"
        )
    return ran(
        "acmg_secondary_findings",
        subjects=report.checked,
        findings=len(report.mismatches),
        source="acmg",
        release=report.version,
        detail="; ".join(parts)
        or f"every stated acmg_sf on {report.checked} row(s) agrees with ACMG SF v{report.version}",
    )
