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
"""

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from just_dna_format.spec import VariantRow

logger = logging.getLogger(__name__)

DEFAULT_ACMG_URL = "https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/"

#: The four column labels the table has carried since NCBI adapted it. A change here means the page
#: was re-laid-out and every offset below is suspect, so it is a refusal rather than a best guess.
EXPECTED_HEADERS = ("Disease name and MIM number", "MedGen", "Gene via GTR", "Variations that may")

#: A floor, not the real count — the real count is whatever ACMG publishes next and hard-coding it
#: would be the hand-transcribed list this module exists to avoid. It catches the cheap disasters: a
#: JavaScript shell, a truncated response, an error page that happens to contain a table.
MIN_GENES = 50

_VERSION_RE = re.compile(r"ACMG\s+SF\s+v(\d+(?:\.\d+)*)")
# Three link shapes, all seen on the live page: /gtr/genes/324, /gtr/genes/4089/, /gene/3949.
_GENE_LINK_RE = re.compile(r'href="/(?:gtr/)?genes?/(\d+)/?"\s*>\s*([A-Za-z0-9_.\-]+)\s*</a>')
_MIM_RE = re.compile(r"MIM\s+(\d+)")
# Read off the cell *text* (`MedGen C1861848, C0031511`), not the href: the multi-concept cells link
# to a MedGen search rather than to a concept page, so the href carries a query and not an id.
_MEDGEN_ID_RE = re.compile(r"\b(C\d{5,})\b")
_TAG_RE = re.compile(r"<[^>]+>")


class AcmgSfError(RuntimeError):
    """An ACMG SF fetch or parse failed in a way the caller must see rather than work around."""


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
    gene_mim: Optional[str] = None
    disease: Optional[str] = None
    disease_mims: tuple[str, ...] = ()
    medgen_ids: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class AcmgVerdict:
    """One `variants.csv` row's answer, over the tri-state the authored column actually has.

    * `agree` — the authored value matches the list, either way round. Silent.
    * `not_listed` — authored True, gene is **not** listed. A finding.
    * `denied` — authored False, gene **is** listed. A finding, and the message names the entry.
    * `unstated` — blank, gene is listed. A note, never a finding: blank means "not stated", and
      turning that into a defect is exactly the `None`-means-`False` collapse this codebase refuses.
    * `blank` — blank, gene is not listed. Nothing was asserted and nothing contradicts it.
    * `unchecked` — the row names no gene, or the list could not be reached. The question was never
      asked, which is not the same as being answered "no".
    """

    row: int
    gene: Optional[str]
    authored: Optional[bool]
    verdict: str
    message: str = ""


@dataclass
class AcmgReport:
    version: Optional[str]
    verdicts: list[AcmgVerdict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def mismatches(self) -> list[AcmgVerdict]:
        """The verdicts that are defects — what `strict` refuses on."""
        return [v for v in self.verdicts if v.verdict in {"not_listed", "denied"}]

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
        raise AcmgSfError(
            f"{source_url} declares no 'ACMG SF vN.N' version — the page changed, and a list with no "
            "version cannot be reported against"
        )
    version = version_match.group(1)

    table = _select_table(text, source_url)
    cells = re.split(r"<td[^>]*>", table)[1:]
    width = len(EXPECTED_HEADERS)
    if not cells or len(cells) % width:
        raise AcmgSfError(
            f"{source_url}: the ACMG table has {len(cells)} cells, which is not a multiple of "
            f"{width} — the column layout changed, so the list cannot be read positionally"
        )

    findings: list[SecondaryFinding] = []
    for index in range(0, len(cells), width):
        disease_cell, medgen_cell, gene_cell, _clinvar_cell = cells[index : index + width]
        links = _GENE_LINK_RE.findall(gene_cell)
        if len(links) != 1:
            raise AcmgSfError(
                f"{source_url}: row {index // width + 1} has {len(links)} gene links in its gene "
                f"cell, expected exactly 1 — refusing rather than returning a list short by a gene "
                f"(cell: {_strip(gene_cell)[:120]!r})"
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
        raise AcmgSfError(
            f"{source_url}: parsed only {len(genes)} distinct genes from ACMG SF v{version}, below "
            f"the {MIN_GENES} floor — the response is truncated or is not the list page"
        )
    logger.info("ACMG SF v%s: %d genes over %d gene-condition rows", version, len(genes), len(findings))
    return AcmgSfList(
        version=version,
        findings=findings,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_url=source_url,
    )


def _select_table(text: str, source_url: str) -> str:
    """The one `<table>` carrying all four expected headers.

    The page has exactly one today, but selecting by header rather than by position means a future
    navigation or footer table cannot silently become "the list"."""
    for match in re.finditer(r"<table[^>]*>(.*?)</table>", text, re.S):
        body = match.group(1)
        header_end = body.find("</tr>")
        header = body[: header_end if header_end != -1 else len(body)]
        if all(label in header for label in EXPECTED_HEADERS):
            return body[header_end + len("</tr>") :] if header_end != -1 else body
    raise AcmgSfError(
        f"{source_url}: no table carries the headers {EXPECTED_HEADERS} — the page was re-laid out"
    )


def fetch_acmg_page(url: str = DEFAULT_ACMG_URL, *, timeout: float = 60.0) -> str:
    """Download the SF page (~75 KB of HTML — one GET, no pacing needed)."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AcmgSfError(f"could not fetch the ACMG secondary-findings page from {url}: {exc}") from exc
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
                AcmgVerdict(
                    index, gene, True, "not_listed",
                    f"acmg_sf=true but {gene} is not on ACMG SF v{sf_list.version} "
                    f"({len(listed)} genes)",
                )
            )
        elif not variant.acmg_sf and on_list:
            verdicts.append(
                AcmgVerdict(
                    index, gene, False, "denied",
                    f"acmg_sf=false but {gene} is on ACMG SF v{sf_list.version} "
                    f"({_conditions(sf_list, gene)}); the column is a gene-level list-membership "
                    f"fact, so leave it blank rather than false if this row is about a variant that "
                    f"is not itself a reportable secondary finding",
                )
            )
        else:
            verdicts.append(AcmgVerdict(index, gene, variant.acmg_sf, "agree"))
    return AcmgReport(version=sf_list.version, verdicts=verdicts)


def _conditions(sf_list: AcmgSfList, gene: str) -> str:
    names = [entry.disease for entry in sf_list.entries_for(gene) if entry.disease]
    return "; ".join(names) if names else "no condition named"


def verify_acmg_sf(
    variants: list[VariantRow],
    *,
    mode: str = "best_effort",
    offline: bool = False,
    url: str = DEFAULT_ACMG_URL,
    page_text: Optional[str] = None,
) -> AcmgReport:
    """Fetch (or accept) the list and check `variants` against it.

    `offline` returns a report of nothing checked rather than a report of nothing found — the same
    `unchecked` ≠ `absent` distinction every other pass in this tier draws. `strict` escalates a
    mismatch to a refusal; list membership is a published fact, not a clinical judgement, so unlike
    the `clin_sig` cross-check there is no reason to hold this one at a warning.
    """
    if offline and page_text is None:
        report = AcmgReport(
            version=None,
            verdicts=[
                AcmgVerdict(index, (v.gene or None), v.acmg_sf, "unchecked", "offline")
                for index, v in enumerate(variants, start=1)
            ],
            warnings=["--offline: the ACMG SF list is live-only, so acmg_sf went unchecked"],
        )
        logger.warning(report.warnings[0])
        return report

    sf_list = parse_acmg_page(page_text if page_text is not None else fetch_acmg_page(url), source_url=url)
    report = check_acmg_sf(variants, sf_list)
    # Findings are the return value, not log output — the tier's convention is that a caller decides
    # how to present them and `logger` carries only what went wrong operationally. Logging them here
    # too would print every mismatch twice under the default root handler.
    logger.info(
        "acmg_sf checked against v%s: %d row(s), %d mismatch(es)",
        sf_list.version, report.checked, len(report.mismatches),
    )
    if mode == "strict" and report.mismatches:
        grouped = AcmgReport.by_gene(report.mismatches)
        raise AcmgSfError(
            f"strict acmg_sf check: {len(report.mismatches)} row(s) across {len(grouped)} gene(s) "
            f"disagree with ACMG SF v{sf_list.version}: "
            + "; ".join(f"{gene} ({len(rows)} row(s)): {message}" for gene, rows, message in grouped)
        )
    return report
