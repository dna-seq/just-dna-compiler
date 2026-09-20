"""A module's own recorded declaration counts at every gate that has a module (S105, RM252).

`pgx` on a module drafted under `--use non-commercial` printed *"cpic forbids sale and no use was
declared"* while the declaration sat in the licence table it had just read, and asked the author to
assert the same position a second time. `effective_declared_use` reads the recorded row when the flag
states nothing; the flag still outranks the file, a declaration for one source says nothing about
another, and `unstated` on disk is not a declaration.
"""

import ast
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.licensing import (
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    effective_declared_use,
    write_sources_csv,
)
from just_dna_enricher.pgx import enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene

_YAML = (
    'schema_version: "1.0"\nmodule:\n  name: probe\n  title: T\n  report_title: T\n  description: d\n'
    "genome_build: GRCh38\n"
)


def _spec(tmp_path: Path, *rows) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "allele_function.csv").write_text(
        "gene,allele,function_status\nCYP2C19,*2,no_function\n", encoding="utf-8"
    )
    if rows:
        write_sources_csv(list(rows), spec / "licensing.csv")
    return spec


def _cpic_row(declared_use: str, layer: str = "annotation"):
    return CPIC_TERMS.row(layer, declared_use=declared_use)


# ── the helper ───────────────────────────────────────────────────────────────────────────────────


def test_the_recorded_declaration_is_read_when_the_flag_states_none(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    assert effective_declared_use(spec, CPIC_TERMS, "unstated") == ("non_commercial", "licensing.csv")


def test_the_flag_outranks_the_file_in_both_directions(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    assert effective_declared_use(spec, CPIC_TERMS, "commercial") == ("commercial", None)
    spec = _spec(tmp_path, _cpic_row("unstated"))
    assert effective_declared_use(spec, CPIC_TERMS, "non-commercial") == ("non_commercial", None)


def test_unstated_on_disk_is_not_a_declaration(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _cpic_row("unstated"))
    assert effective_declared_use(spec, CPIC_TERMS, "unstated") == ("unstated", None)


def test_a_declaration_is_per_source_and_per_layer(tmp_path: Path) -> None:
    """CPIC's row says nothing about PharmVar, and a row at another layer is another pass's."""
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    assert effective_declared_use(spec, PHARMVAR_TERMS, "unstated") == ("unstated", None)
    spec = _spec(tmp_path, _cpic_row("non_commercial", layer="resolution"))
    assert effective_declared_use(spec, CPIC_TERMS, "unstated") == ("unstated", None)


def test_no_licence_table_means_unstated(tmp_path: Path) -> None:
    assert effective_declared_use(_spec(tmp_path), CPIC_TERMS, "unstated") == ("unstated", None)


# ── the pgx check, the report's own command ─────────────────────────────────────────────────────


def test_pgx_runs_the_cpic_leg_on_the_recorded_declaration(tmp_path: Path, no_ambient_caches) -> None:
    """Before: `not_permitted` with "no use was declared". After: the gate passes, the leg reaches its
    route (offline, no snapshot here — a different skip, with a different remedy), and the summary
    can say where the declaration was read from. PharmVar has no row and still asks."""
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    result = enrich_pgx(spec, offline=True)

    assert not any("cpic" in reason for reason in result.skipped), result.skipped
    assert any("cpic" in note for note in result.skipped_offline), result.skipped_offline
    assert result.recorded_use == {"cpic": "non_commercial"}
    assert result.declared_use == "unstated"  # the flag, reported as the flag
    [pharmvar] = [reason for reason in result.skipped if "pharmvar" in reason]
    assert "no use was declared" in pharmvar


def test_pgx_still_refuses_a_commercial_flag_over_a_recorded_non_commercial_row(
    tmp_path: Path, no_ambient_caches
) -> None:
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    with pytest.raises(LicenseRefusal):
        enrich_pgx(spec, offline=True, declared_use="commercial", use_pharmvar=False)


def test_pgx_with_an_unstated_row_says_no_use_was_declared_as_before(
    tmp_path: Path, no_ambient_caches
) -> None:
    spec = _spec(tmp_path, _cpic_row("unstated"))
    result = enrich_pgx(spec, offline=True, use_pharmvar=False)
    [reason] = result.skipped
    assert "cpic" in reason and "no use was declared" in reason
    assert result.recorded_use == {}


# ── the drafter, where the declaration was first recorded ───────────────────────────────────────


def test_a_second_draft_reads_the_declaration_the_first_one_recorded(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gene"):
            return httpx.Response(200, json=[{"symbol": "CYP2C19", "chr": "chr10"}])
        return httpx.Response(200, json=[])

    from just_dna_enricher.cpic import CpicClient

    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    spec = _spec(tmp_path, _cpic_row("non_commercial"))
    result = draft_gene(spec, "CYP2C19", client=client)  # no declaration passed
    assert not result.skipped
    [note] = [w for w in result.warnings if "licensing.csv" in w]
    assert "non_commercial" in note and "--use" in note


# ── every gate with a module directory goes through the helper ──────────────────────────────────


def _gates() -> dict[str, set[str]]:
    """`module.function` for every function calling `check_declared_use`, split by whether the same
    function calls `effective_declared_use` first. A nested `def`'s calls are its own, not its
    parent's (`@licence-row-inside-the-commit`), which is what makes `pgx.consult` the site."""
    src = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"
    through: set[str] = set()
    direct: set[str] = set()
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        for node in functions:
            inner = {id(n) for f in functions if f is not node and f in ast.walk(node) for n in ast.walk(f)}
            own = [
                n.func.id
                for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and id(n) not in inner
            ]
            if "check_declared_use" not in own:
                continue
            label = f"{path.stem}.{node.name}"
            if "effective_declared_use" in own and own.index("effective_declared_use") < own.index(
                "check_declared_use"
            ):
                through.add(label)
            else:
                direct.add(label)
    return {"through": through, "direct": direct}


def test_every_gate_with_a_module_reads_its_recorded_declaration() -> None:
    """Set equality over the walked call sites, never a floor. The direct callers are the two that
    have no module to read — the cache lanes (`caches`, `cli`) gate a download, not a module — and
    the helper itself. A new provider gating a fetch inside a module lands in `through` or fails here."""
    gates = _gates()
    assert gates["through"] == {
        "clinpgx.enrich_clinpgx",
        "clinpgx_draft.draft_pharm_variants",
        "clinvar_draft.draft_gene_panel",
        "drug_labels.check_drug_labels",
        "expression.enrich_expression",
        "mitomap_draft.draft_panel_from_mitomap_miss",
        "pgx.consult",
        "pgx_draft.draft_gene",
        "strchive_draft.draft_repeat_loci",
    }, gates
    assert gates["direct"] == {
        "caches._gate",
        "caches.prepare_lane",
        "cli.cache_pull_",
        "cli.clinpgx_build_",
        "cli.clinpgx_build_labels_",
        "cli.cpic_build_",
        "cli.pharmvar_build_",
    }, gates
