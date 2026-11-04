"""The resolution step, once, for both commands (RM367).

`validate_spec` is the pre-flight for `compile_module` (`@validate-refuses-all`), and resolution is where
the two kept learning to disagree: each read `resolution.csv` in its own loop, and the compile then ran
`resolve_from_table` and a run of checks over the resolved rows that the pre-flight had no copy of. The
standing exemption said a check over *resolved* rows is compile-only. It never held for this table:
resolving it is pure computation over bytes the pre-flight has already loaded, and asks no reference and
no network. What the pre-flight genuinely cannot see is a reference it is not handed, the deprecated
`ensembl_cache`, so that path stays the compile's alone and is the one entry left in `check_paths`.

Three functions, each called by both commands:

* `read_resolution` reads the table and returns the **active** view. Under `--no-resolve` the view is
  empty, and every consumer reads the view, so the switch reaches every check, count, signature and
  writer at once rather than one at a time (`@off-switch-needs-a-probe`). The file is still parsed, for
  the row count the `resolution_disabled` warning publishes and for its own load errors.
* `resolve_variants` fills and expands `variants.csv` from the active view, or says that nothing was
  injected, and returns the refusals in the strings the compile publishes.
* `after_resolution` is what the resolved rows owe: the identity checks an expansion can break, the
  ploidy guardrail on the `chrom` resolution filled, and the strict aggregate over rows still unplaced.
"""

from dataclasses import dataclass, field
from pathlib import Path

from just_dna_format.findings import CodedWarning
from just_dna_format.overrides import OverrideRow, apply_overrides, update_targets
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_compiler.compiler.load import _load_csv_rows
from just_dna_compiler.compiler.manifest import _snapshot_unplaced_rsids_recorded
from just_dna_compiler.compiler.table_checks import _validate_table_kind
from just_dna_compiler.compiler.tables import _locate_sidecar
from just_dna_compiler.compiler.variant_checks import (
    _check_build_coordinates,
    _check_contig_ploidy,
    _CoordinateTable,
    _cross_validate_variants,
)
from just_dna_compiler.compiler.vrs_checks import _verify_vrs_ids, _vrs_coverage_warnings
from just_dna_compiler.resolution import resolve_from_table
from just_dna_compiler.resolution_findings import resolution_not_injected

RESOLUTION_CSV = "resolution.csv"


@dataclass
class InjectedResolution:
    """`resolution.csv` as both commands read it: located, parsed, overlaid, self-checked.

    `rows` is the active view — post-overlay, and **empty under `--no-resolve`**. `loaded` is every row
    the file parsed to, read only for the size of what the switch skipped. `present` answers whether the
    module carries the file at all, which the overlay's missing-target warning asks, whatever the switch.
    `deferred` is RM137's stash of unmatched `update` targets, `None` when the view is inactive.
    `consulted` says the view is active: the file parsed and the switch is on.
    """

    present: bool = False
    loaded: list[ResolutionRow] = field(default_factory=list)
    rows: list[ResolutionRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deferred: list[tuple[tuple[str, str], bool]] | None = None
    #: The file parsed and the switch is on: `rows` is what the module asserts.
    consulted: bool = False

    @property
    def table(self) -> dict[str, list[ResolutionRow]]:
        """The active rows by `variant_key`, in file order — what resolution and membership look up."""
        return _by_key(self.rows)

    @property
    def named_table(self) -> dict[str, list[ResolutionRow]]:
        """What a diagnosis may NAME: the active view, or under `--no-resolve` every row the file holds.

        Only for a sentence saying what was skipped (the positional joinability report's "resolution.csv
        names N of them and was not consulted"); nothing reads it to place, verify or count a row.
        """
        return self.table if self.consulted else _by_key(self.loaded)


def _by_key(rows: list[ResolutionRow]) -> dict[str, list[ResolutionRow]]:
    by_key: dict[str, list[ResolutionRow]] = {}
    for row in rows:
        by_key.setdefault(row.variant_key, []).append(row)
    return by_key


def resolution_disabled(rows: list[ResolutionRow]) -> CodedWarning:
    """The `--no-resolve` notice, with the size of what it skipped (rows, and the keys they cover)."""
    keys = len({row.variant_key for row in rows})
    return CodedWarning(
        "resolution_disabled",
        f"--no-resolve (resolve_with_ensembl=False) switches off resolution entirely, including "
        f"the injected resolution.csv beside this spec ({len(rows)} row(s), covering "
        f"{keys} variant key(s)), which was not read — every variant will compile "
        f"with no chrom/start and match no VCF. The flag names Ensembl but is the master switch; "
        f"drop it to use the injected table. There is no flag for 'do not reach the network' "
        f"because the compiler never does (CONSTITUTION P2) — omitting this one is that request.",
    )


def read_resolution(spec_dir: Path, overrides: list[OverrideRow], *, resolve: bool) -> InjectedResolution:
    """Read `resolution.csv` into the view every consumer reads (see the module docstring).

    The self-checks run here, on the active rows only: the table-kind coherence check, `_verify_vrs_ids`
    (a mismatch refuses in both modes) and the VRS coverage count. Under `--no-resolve` none of them
    runs, because none of what they judge reaches the artifact.
    """
    out = InjectedResolution()
    path, spelling_warnings, spelling_errors = _locate_sidecar(spec_dir, RESOLUTION_CSV)
    out.warnings.extend(spelling_warnings)
    out.errors.extend(spelling_errors)
    if path is None:
        return out
    out.present = True
    loaded, load_errors, load_warnings = _load_csv_rows(path, ResolutionRow, path.name)
    out.errors.extend(load_errors)
    out.warnings.extend(load_warnings)
    if load_errors:
        return out
    out.loaded = loaded
    if not resolve:
        if loaded:
            out.warnings.append(resolution_disabled(loaded))
        return out
    out.consulted = True
    # Deferred and stashed on the PRE-overlay rows (RM137): `apply_overrides` rebinds its input, and an
    # `insert` earlier in the same overlay would otherwise make a later update look matched.
    out.deferred = update_targets(RESOLUTION_CSV, loaded, overrides)
    rows, apply_errors, apply_warnings = apply_overrides(
        RESOLUTION_CSV, loaded, overrides, defer_unmatched=True
    )
    out.errors.extend(apply_errors)
    out.warnings.extend(apply_warnings)
    out.rows = rows
    if rows:
        tbl_errors, tbl_warnings = _validate_table_kind(path.name, ResolutionRow, rows)
        out.errors.extend(tbl_errors)
        out.warnings.extend(tbl_warnings)
    vrs_errors, vrs_warnings = _verify_vrs_ids(rows)
    out.errors.extend(vrs_errors)
    out.warnings.extend(vrs_warnings)
    out.warnings.extend(
        _vrs_coverage_warnings(rows, unplaced_recorded=_snapshot_unplaced_rsids_recorded(spec_dir))
    )
    return out


@dataclass
class ResolvedVariants:
    """`variants.csv` after the injected table was applied, and what applying it found.

    `refusals` holds the strings the compile publishes, prefixed as it publishes them: `resolution: …`
    (fatal in both modes) and, under `strict`, `strict resolution: …` (the round-trip ladders, routed
    through `route`, RM359). `expanded_keys`/`expanded_rows` are S33's counts, `None` where no table was
    applied.
    """

    variants: list[VariantRow]
    refusals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expanded_keys: int | None = None
    expanded_rows: int | None = None


def resolve_variants(
    variants: list[VariantRow],
    table: dict[str, list[ResolutionRow]],
    genome_build: str,
    *,
    strict: bool,
) -> ResolvedVariants:
    """Apply the active table to `variants`, or say once that nothing was injected.

    The caller decides whether resolution runs at all (`resolve_with_ensembl`, and the compile's
    deprecated `ensembl_cache` path, which places rows this function cannot see).
    """
    if table:
        outcome = resolve_from_table(variants, table, genome_build=genome_build)
        strict_refusals, warnings = outcome.channels(strict=strict)
        return ResolvedVariants(
            variants=outcome.variants,
            refusals=[f"resolution: {e}" for e in outcome.errors]
            + [f"strict resolution: {e}" for e in strict_refusals],
            warnings=warnings,
            expanded_keys=outcome.expanded_keys,
            expanded_rows=outcome.expanded_rows,
        )
    if any(v.chrom is None or v.start is None for v in variants):
        # Nothing injected: the compiler never auto-discovers or fetches a reference (P2). Said once,
        # rather than blaming a file that does not exist once per variant.
        return ResolvedVariants(
            variants=variants,
            warnings=[
                CodedWarning(
                    "resolution_not_injected",
                    resolution_not_injected(
                        missing="No resolution.csv and no ensembl_cache injected",
                        remedy="Produce a resolution.csv with just-dna-enricher.",
                    ),
                )
            ],
        )
    return ResolvedVariants(variants=variants)


def identity_after_resolution(variants: list[VariantRow], genome_build: str) -> list[str]:
    """The identity checks an expansion or a fill can break, over the resolved rows, prefixed.

    Filling a coordinate or expanding a one-to-many rsID may collide with an already-authored row, and a
    filled coordinate must be possible in the build. The pre-flight ran both over the authored rows; these
    are the resolved rows' answers.
    """
    cross_errors, _ = _cross_validate_variants(variants)
    build_errors = _check_build_coordinates([_CoordinateTable("variants.csv", genome_build, True, variants)])
    return [f"post-resolution: {e}" for e in [*cross_errors, *build_errors]]


def ploidy_after_resolution(variants: list[VariantRow], genome_build: str) -> list[str]:
    """The non-diploid guardrail where `chrom` is final — an rsID-authored MT or Y row has one only now."""
    return _check_contig_ploidy(variants, genome_build)


def unplaced_refusal(variants: list[VariantRow]) -> list[str]:
    """`strict`'s all-or-nothing aggregate: rows that still carry no position once resolution is done.

    Over the rows resolution left, whatever left them unplaced: no table, a table without the key, a
    non-GRCh38 module (which the table path skips wholesale), every candidate locus rejected, or
    `--no-resolve`. RM359 kept this aggregate out of its one-channel rule on purpose — it is a different
    finding from the per-subject warnings beside it — and that decision stands here.
    """
    unresolved = sorted(v.rsid or v.variant_key for v in variants if v.chrom is None or v.start is None)
    if not unresolved:
        return []
    return [
        f"strict compile: {len(unresolved)} variant(s) have unresolved genomic "
        f"positions after resolution: {unresolved}. A partial artifact would not be "
        f"byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or "
        f"compile without strict."
    ]
