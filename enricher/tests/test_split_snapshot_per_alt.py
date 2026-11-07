"""RM381: every reader of a snapshot hands on each ALT in its own spelling, never the site's shared padded `ref`.

The split Ensembl repo (`ensembl_variations_split`, RM372) stores a multi-ALT indel site as one row per ALT,
all under one padded `ref`: `rs1555461597` is `16:23635706 GTT>G`, `GTT>GT` and `GTT>GTTT`. The readers
regrouped those rows into one locus, `GTT>G,GT,GTTT`, and nothing trimmed an ALT against the ref. So the
caller's per-ALT spelling (`G>GT`, `GT>G`) was never written, offline or online: offline nothing can be
left-aligned, and online `_filled_pieces` read `G/GT` in the padded frame as a compound het of two
deletions and kept the locus whole. Re-enriching `hboc_palb2` and `pathogenic_clinvar` against the split
snapshot cost `test_consumer_join` six alleles.

The fixture is the real rows (`assets/ensembl_split_multialt/`), and the oracle is ClinVar's own per-ALT
records for the two rsIDs in the consumer-join slice, which is what a caller writes.
"""

import ast
import gzip
import re
from collections.abc import Callable
from pathlib import Path

import duckdb
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.resolution import hosting_verdict, site_verdicts
from just_dna_enricher import clinvar, ensembl, gnomad, resolver
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.orchestration import _filled_pieces
from just_dna_format import alleles

_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = _ROOT / "assets" / "ensembl_split_multialt"
SPLIT = FIXTURE / "split"
OLD = FIXTURE / "old"
CONSUMER_JOIN = _ROOT / "assets" / "consumer_join"
ENRICHER_SRC = _ROOT / "enricher" / "src" / "just_dna_enricher"

#: The rows' authored genotypes in `hboc_palb2`, `pathogenic_clinvar` and `shox_par1` (drafted from ClinVar).
#: SHOX's `C/CAG` read in the padded frame `CAG>C,CAGAG` names only the deletion (`CAG` is the ref), so
#: re-deriving `shox_par1` against the split repo lost the duplication RM270 had written beside it.
GENOTYPES = {"rs1555461597": "G/GT", "rs267607291": "T/TG", "rs1569493663": "C/CAG"}

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)

Spelling = tuple[str, int, str, str]


def _clinvar_records(rsid: str) -> set[Spelling]:
    """ClinVar's per-ALT records for one rsID in the consumer-join slice: the spelling a caller writes."""
    number = rsid.removeprefix("rs")
    out: set[Spelling] = set()
    with gzip.open(CONSUMER_JOIN / "clinvar_20260627_norm_slice.vcf.gz", "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            chrom, pos, _id, ref, alt, *_rest, info = line.rstrip("\n").split("\t")
            if f"RS={number}" in info.split(";"):
                out.add((chrom, int(pos), ref, alt))
    return out


def _hosted(rsid: str) -> set[Spelling]:
    """ClinVar's records for the rsID that can host the module's genotype."""
    return {s for s in _clinvar_records(rsid) if hosting_verdict(GENOTYPES[rsid], s[2], s[3]) is not False}


def _window(chrom: str, start: int, end: int) -> str | None:
    """1-based inclusive GRCh38 bases from the consumer-join fixture's windows (`samtools faidx`)."""
    with gzip.open(CONSUMER_JOIN / "grch38_windows.fa.gz", "rt") as handle:
        records = handle.read().split(">")[1:]
    for record in records:
        header, _, body = record.partition("\n")
        name, span = header.rsplit(":", 1)
        first = int(span.split("-")[0])
        bases = body.replace("\n", "").upper()
        if name == chrom and first <= end <= first + len(bases) - 1:
            return bases[max(start, first) - first : end - first + 1]
    return None


def _per_alt(loci: list[dict]) -> set[Spelling]:
    return {
        (str(lo["chrom"]), int(lo["start"]), str(lo["ref"]), alt)  # type: ignore[arg-type]
        for lo in loci
        for alt in str(lo["alts"]).split(",")
    }


def _padded_loci(snapshot: Path) -> dict[str, list[dict]]:
    """Each rsID's rows as the snapshot spells them, one locus per (chrom, start, ref) — no reader involved."""
    frame = pl.read_parquet(next((snapshot / "data").glob("*.parquet")))
    out: dict[str, list[dict]] = {}
    for (rsid, chrom, start, ref), group in frame.group_by(
        ["id", "chrom", "start", "ref"], maintain_order=True
    ):
        alts = sorted({a for cell in group["alt"] for a in cell.split("|") if a})
        out.setdefault(str(rsid), []).append(
            {"chrom": chrom, "start": int(start), "ref": ref, "alts": ",".join(alts)}
        )
    return out


# ── the fixture is what the class needs: one padded ref shared by several ALTs ──────────────────────


def test_the_fixture_holds_each_site_under_one_padded_ref_the_callers_spelling_does_not_use() -> None:
    padded = _padded_loci(SPLIT)
    for rsid in GENOTYPES:
        (locus,) = padded[rsid]
        assert len(locus["alts"].split(",")) > 1
        # The padded spelling is not ClinVar's for at least one ALT, or there would be nothing to fix.
        assert not _per_alt([locus]) <= _clinvar_records(rsid)


# ── the reader: offline, the split rows reach the module in the caller's per-ALT spelling ──────────


def _spec(root: Path, rows: list[str], header: str = "rsid,genotype,state,conclusion") -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return spec


def test_offline_a_filled_multi_alt_indel_is_written_in_the_callers_per_alt_spelling(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """The fill needs no reference read: trimming an ALT against the shared ref is string work. The
    pieces are not proven leftmost offline, so `left_aligned` says unknown, never true."""
    spec = _spec(tmp_path, [f"{rsid},{genotype},risk,c" for rsid, genotype in GENOTYPES.items()])
    result = enrich(spec, offline=True, ensembl_cache=SPLIT, clinvar_cache=tmp_path / "no_clinvar")
    assert result.unresolved == []
    for rsid in GENOTYPES:
        rows = [r for r in result.rows if r.rsid == rsid]
        written = {(r.chrom, r.start, r.ref, alt) for r in rows for alt in (r.alts or "").split(",")}
        assert written == _hosted(rsid), rsid
        assert {r.left_aligned for r in rows} == {None}


def test_offline_the_position_back_fill_meets_a_caller_spelled_coordinate(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """The mirror: a row authored in the caller's spelling (`16:23635706 GT>G`) never equalled the
    padded `GTT>GT` row, so no rsID was back-filled from the split snapshot."""
    wanted = {s: rsid for rsid in GENOTYPES for s in _hosted(rsid)}
    rows = [f"{c},{p},{r},{a},{'/'.join(sorted((r, a)))},risk,c" for c, p, r, a in sorted(wanted)]
    spec = _spec(tmp_path, rows, header="chrom,start,ref,alts,genotype,state,conclusion")
    result = enrich(spec, offline=True, ensembl_cache=SPLIT, clinvar_cache=tmp_path / "no_clinvar")
    back = {(r.chrom, r.start, r.ref, r.alts): r.rsid for r in result.rows}
    assert back == wanted


# ── parity: the split rows and the old pipe-joined row give one caller spelling per ALT ─────────────


def _written(
    snapshot: Path,
    rsid: str,
    read_window: Callable[[str, int, int], str | None] | None,
    genotype: str | None = None,
) -> set[Spelling]:
    """What `enrich` writes for an rsID-only row: the reader's loci, the site-framed hosting filter
    (`site_verdicts`, what `enrich` asks), then RM270's fill."""
    loci, _, _ = resolver.lookup_loci(snapshot, [rsid], [])
    genotype = genotype or GENOTYPES[rsid]
    spellings = [(lo["chrom"], lo["start"], lo["ref"], lo["alts"]) for lo in loci[rsid]]
    hosted = [
        lo for lo, ok in zip(loci[rsid], site_verdicts(genotype, spellings), strict=True) if ok is not False
    ]
    return _per_alt([piece for lo in hosted for piece, _ in _filled_pieces(genotype, lo, read_window)])


@pytest.mark.parametrize("rsid", sorted(GENOTYPES))
def test_online_the_split_rows_and_the_old_row_write_one_spelling_and_it_is_the_callers(rsid: str) -> None:
    """Both old rows were right-shifted, so the old snapshot was right only online, by left-alignment.
    Online, the two snapshots must agree with each other and with ClinVar."""
    assert _written(SPLIT, rsid, _window) == _written(OLD, rsid, _window) == _hosted(rsid)


@pytest.mark.parametrize("rsid", sorted(GENOTYPES))
def test_offline_trimming_alone_reaches_the_callers_spelling_on_the_split_rows(rsid: str) -> None:
    """The split repo anchors left, so for these sites the trim is the whole normalization; the old
    repo's right-shifted rows still need the reference, which is why its parity above is online."""
    assert _written(SPLIT, rsid, None) == _hosted(rsid)


# ── both sides' raw tokens: a genotype in a site's padded frame names the piece its trimmed form does ──
#: `(rsid, the event's caller spelling, the split repo's padded genotype, the old repo's padded genotype)`.
#: Each padded genotype is the ref and the one ALT of that record's own frame, so it names the event alone;
#: the caller's ref/ALT pair (`G/GT`, `C/CAG`) also reads as the other ALT, RM270's either-reading rule.
FRAMED = [
    ("rs1555461597", ("16", 23635706, "G", "GT"), "GTT/GTTT", "TT/TTT"),
    ("rs1569493663", ("X", 634689, "C", "CAG"), "CAG/CAGAG", "AGA/AGAGA"),
]


@pytest.mark.parametrize(("rsid", "event", "split_frame", "old_frame"), FRAMED)
def test_a_genotype_in_the_split_rows_padded_frame_names_its_event_alone(
    rsid: str, event: Spelling, split_frame: str, old_frame: str
) -> None:
    """Padded genotype against the split rows, offline and online: one piece, the event's."""
    assert _written(SPLIT, rsid, None, split_frame) == {event}
    assert _written(SPLIT, rsid, _window, split_frame) == {event}


@pytest.mark.parametrize(("rsid", "event", "split_frame", "old_frame"), FRAMED)
def test_a_genotype_in_the_old_rows_padded_frame_names_its_event_alone(
    rsid: str, event: Spelling, split_frame: str, old_frame: str
) -> None:
    """Padded genotype against the old pipe-joined row (`AGA/AGAGA` is the duplication alone in
    `X:634690 AGA>A|AGAGA`), online, where the old right-shifted row reaches the caller's spelling."""
    assert _written(OLD, rsid, _window, old_frame) == {event}


@pytest.mark.parametrize(("rsid", "event", "split_frame", "old_frame"), FRAMED)
def test_the_trimmed_genotype_names_the_event_on_both_snapshots(
    rsid: str, event: Spelling, split_frame: str, old_frame: str
) -> None:
    """The caller's spelling against both repos: the event, plus the other ALT it also reads as, the same
    set on both, and ClinVar's per-ALT records of that pair."""
    trimmed = "/".join(sorted((event[2], event[3])))
    written = _written(SPLIT, rsid, _window, trimmed)
    assert event in written and written == _written(OLD, rsid, _window, trimmed) == _written(
        SPLIT, rsid, None, trimmed
    )


def test_a_compound_het_in_the_padded_frame_finds_both_its_pieces(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """`G/GTTT` read in the split repo's frame `GTT>G,GT,GTTT` is the 2 bp deletion and the 1 bp insertion:
    each allele trims to one piece, so both are written and the compile hosts it on both, offline. A
    published module authored from such a record keeps behaving (P3)."""
    spec = _spec(tmp_path, ["rs1555461597,G/GTTT,risk,c"])
    (spec / "studies.csv").write_text("rsid,pmid\nrs1555461597,9545397\n", encoding="utf-8")
    result = enrich(spec, offline=True, ensembl_cache=SPLIT, clinvar_cache=tmp_path / "no_clinvar")
    assert result.allele_mismatches == []
    written = {(r.chrom, r.start, r.ref, r.alts) for r in result.rows if r.chrom is not None}
    assert written == {("16", 23635706, "GTT", "G"), ("16", 23635706, "G", "GT")}
    compiled = compile_module(spec, tmp_path / "out", strict=True)
    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet")
    assert {
        (c, s, r, tuple(a)) for c, s, r, a in weights.select("chrom", "start", "ref", "alts").iter_rows()
    } == {
        ("16", 23635706, "GTT", ("G",)),
        ("16", 23635706, "G", ("GT",)),
    }
    assert not [w for w in compiled.warnings if "not_at_locus" in str(w) or "cannot host" in str(w)]


def test_site_verdicts_read_one_frame_per_site_and_leave_other_sites_alone() -> None:
    """The ladder on the split pieces, and a paralog at another site keeping its own verdict."""
    pieces = [("16", 23635706, "G", "GT"), ("16", 23635706, "GT", "G"), ("16", 23635706, "GTT", "G")]
    assert site_verdicts("G/GT", pieces) == [
        True,
        True,
        False,
    ]  # ref/ALT in G and in GT; never GTT's two deletions
    assert site_verdicts("GTT/GTTT", pieces) == [True, False, False]
    assert site_verdicts("G/GTTT", pieces) == [
        True,
        False,
        True,
    ]  # a compound het only when no ref/ALT reading
    elsewhere = ("2", 100, "GT", "G")
    assert site_verdicts("GTT/GTTT", [*pieces, elsewhere]) == [
        True,
        False,
        False,
        hosting_verdict("GTT/GTTT", "GT", "G"),
    ]
    # No frame names every allele: per-locus `hosting_verdict`, as before.
    assert site_verdicts("C/T", [("1", 5, "G", "A")]) == [hosting_verdict("C/T", "G", "A")]


# ── the mechanism: every reader goes through one helper ─────────────────────────────────────────────


def _clinvar_shaped(root: Path) -> Path:
    """The split rows as a ClinVar-shaped snapshot (`rsid`, not `id`): the same reader shape, the other table."""
    frame = pl.read_parquet(next((SPLIT / "data").glob("*.parquet"))).rename({"id": "rsid"})
    data = root / "clinvar" / "data"
    data.mkdir(parents=True)
    frame.select("chrom", "start", "ref", "alt", "rsid").write_parquet(data / "clinvar-split.parquet")
    return root / "clinvar"


def _forward_ensembl(tmp_path: Path) -> dict[str, set[Spelling]]:
    con = resolver._connect(SPLIT)
    try:
        loci = resolver._lookup_positions_by_rsid(con, sorted(GENOTYPES), [])
    finally:
        con.close()
    return {rsid: _per_alt(loci[rsid]) for rsid in GENOTYPES}


def _forward_clinvar(tmp_path: Path) -> dict[str, set[Spelling]]:
    con = clinvar._connect(_clinvar_shaped(tmp_path))
    try:
        loci = clinvar._lookup_positions_by_rsid(con, sorted(GENOTYPES), [])
    finally:
        con.close()
    return {rsid: _per_alt(loci[rsid]) for rsid in GENOTYPES}


def _forward_rest(tmp_path: Path) -> dict[str, set[Spelling]]:
    """REST's `allele_string` is the same joint frame (`GTT/G/GT/GTTT`), built here from the real rows."""
    out: dict[str, set[Spelling]] = {}
    for rsid, (locus,) in _padded_loci(SPLIT).items():
        if rsid not in GENOTYPES:
            continue
        payload = {
            "mappings": [
                {
                    "assembly_name": "GRCh38",
                    "seq_region_name": locus["chrom"],
                    "start": locus["start"],
                    "allele_string": "/".join([locus["ref"], *locus["alts"].split(",")]),
                }
            ]
        }
        loci, _, _, _ = ensembl._loci_from_rest(payload, lambda chrom, pos: None)
        out[rsid] = _per_alt(loci)
    return out


def _back_fill(
    lookup: Callable[[duckdb.DuckDBPyConnection, list], Callable[[Spelling], set[str]]],
) -> Callable[[Path], dict[str, set[Spelling]]]:
    """A position→rsID reader, asked at every caller spelling: at which of them does it name the rsID."""

    def run(tmp_path: Path) -> dict[str, set[Spelling]]:
        spellings = sorted({s for rsid in GENOTYPES for s in _clinvar_records(rsid)})
        con = resolver._connect(SPLIT)
        try:
            answers = lookup(con, spellings)
        finally:
            con.close()
        return {rsid: {s for s in spellings if rsid in answers(s)} for rsid in GENOTYPES}

    return run


def _candidates(con: duckdb.DuckDBPyConnection, spellings: list) -> Callable[[Spelling], set[str]]:
    found = resolver._lookup_rsid_candidates(con, "ensembl_variations", "id", spellings)
    return lambda s: set(found.get(s, []))


def _id_sets(con: duckdb.DuckDBPyConnection, spellings: list) -> Callable[[Spelling], set[str]]:
    found = resolver._lookup_rsid_sets_by_position(con, [(c, p, r) for c, p, r, _ in spellings])
    return lambda s: found.get(f"{s[0]}:{s[1]}:{s[2]}", set())


def _first_id(con: duckdb.DuckDBPyConnection, spellings: list) -> Callable[[Spelling], set[str]]:
    found = resolver._lookup_rsids_by_position(con, [(c, p, r) for c, p, r, _ in spellings], [])
    return lambda s: {found[f"{s[0]}:{s[1]}:{s[2]}"]} if f"{s[0]}:{s[1]}:{s[2]}" in found else set()


def _forward_gnomad(tmp_path: Path) -> dict[str, set[Spelling]]:
    """gnomAD's `chrom-pos-ref-alt` ids folded into loci, one id per split row (a padded id is its worst case)."""
    frame = pl.read_parquet(next((SPLIT / "data").glob("*.parquet")))
    out: dict[str, set[Spelling]] = {}
    for rsid in GENOTYPES:
        ids = [
            f"{r['chrom']}-{r['start']}-{r['ref']}-{r['alt']}"
            for r in frame.filter(pl.col("id") == rsid).iter_rows(named=True)
        ]
        out[rsid] = _per_alt(gnomad._loci_from_variant_ids(ids))
    return out


#: Every reader of a snapshot's `alt`, keyed by `module.function` as `test_every_snapshot_reader_is_registered`
#: walks them. A forward reader gives each ALT exactly ClinVar's spelling; a position reader names the
#: rsID at every ClinVar spelling it has (`_lookup_rsids_by_position` picks ONE id per `chrom:start:ref`,
#: so it is held to the spellings whose ref no other rsID at the site carries).
READERS: dict[str, Callable[[Path], dict[str, set[Spelling]]]] = {
    "resolver._lookup_positions_by_rsid": _forward_ensembl,
    "clinvar._lookup_positions_by_rsid": _forward_clinvar,
    "ensembl._loci_from_rest": _forward_rest,
    "gnomad._loci_from_variant_ids": _forward_gnomad,
    "resolver._lookup_rsid_candidates": _back_fill(_candidates),
    "resolver._lookup_rsid_sets_by_position": _back_fill(_id_sets),
    "resolver._lookup_rsids_by_position": _back_fill(_first_id),
}

#: Functions that read `alt` off a snapshot table and are no regrouping reader, each with its reason.
NOT_READERS: dict[str, str] = {
    "clinvar.lookup_clin_sig": "allele-exact join on ClinVar's own per-record caller spelling; regroups nothing",
    "clinvar.select_by_gene": "drafts one row per ClinVar record, in ClinVar's own per-record spelling",
}


def _unshared(rsid: str) -> set[Spelling]:
    """ClinVar's spellings of the rsID whose `chrom:start:ref` no other rsID's row at the site spells."""
    others = {
        (lo["chrom"], lo["start"], lo["ref"])
        for other, loci in _padded_loci(SPLIT).items()
        if other != rsid
        for lo in loci
    }
    return {s for s in _clinvar_records(rsid) if s[:3] not in others}


@pytest.mark.parametrize("name", sorted(READERS))
def test_every_reader_hands_on_each_alt_in_its_callers_spelling(name: str, tmp_path: Path) -> None:
    answered = READERS[name](tmp_path)
    for rsid in GENOTYPES:
        expected = _unshared(rsid) if name == "resolver._lookup_rsids_by_position" else _clinvar_records(rsid)
        assert answered[rsid] == expected, (name, rsid)


def _snapshot_sql_functions() -> set[str]:
    """`module.function` for every function whose SQL reads `alt` from a snapshot table.

    Read off the unparsed body with the docstring dropped, so an f-string's `FROM {table}` is seen as
    written and prose naming a table is not."""
    found: set[str] = set()
    for path in sorted(ENRICHER_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = node.body[1:] if ast.get_docstring(node) is not None else node.body
            text = "\n".join(ast.unparse(statement) for statement in body)
            reads = any(f"FROM {table}" in text for table in ("ensembl_variations", "clinvar", "{table}"))
            if reads and re.search(r"\balt\b", text):
                found.add(f"{path.stem}.{node.name}")
    return found


def _calls(module: str, function: str) -> set[str]:
    """Names a function calls, closed over the helpers its own module defines (so a wrapper counts)."""
    tree = ast.parse((ENRICHER_SRC / f"{module}.py").read_text(encoding="utf-8"))
    defined = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    seen: set[str] = set()
    pending = [function]
    while pending:
        node = defined[pending.pop()]
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name | ast.Attribute):
                name = call.func.id if isinstance(call.func, ast.Name) else call.func.attr
                if name not in seen:
                    seen.add(name)
                    if name in defined and name != function:
                        pending.append(name)
    return seen


def test_every_snapshot_reader_is_registered() -> None:
    """A new reader of a snapshot's `alt` fails here until it is placed: a reader, or not one, with a reason."""
    unsql = {"ensembl._loci_from_rest", "gnomad._loci_from_variant_ids"}  # a payload parser, no SQL
    assert _snapshot_sql_functions() == (set(READERS) - unsql) | set(NOT_READERS)


def _alts_joiners() -> set[str]:
    """`module.function` for every function that builds a locus dict whose `alts` joins several alleles."""
    found: set[str] = set()
    for path in sorted(ENRICHER_SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            for d in ast.walk(node):
                if isinstance(d, ast.Dict) and any(
                    isinstance(k, ast.Constant)
                    and k.value == "alts"
                    and isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Attribute)
                    and v.func.attr == "join"
                    for k, v in zip(d.keys, d.values, strict=True)
                ):
                    found.add(f"{path.stem}.{node.name}")
    return found


def test_only_the_helper_groups_alleles_into_a_locus() -> None:
    """The regroup itself, whatever the reader reads (SQL, a payload, polars): `per_alt_loci` groups trimmed
    ALTs, and `normalize_locus` groups ALTs it has just left-aligned one by one. A third function joining
    `alts` under one ref is a reader grouping by a source's spelling, and fails here (it found gnomAD's)."""
    assert _alts_joiners() == {"sequences.per_alt_loci", "sequences.normalize_locus"}


def test_a_clinvar_record_with_no_alt_is_present_never_absent(tmp_path: Path) -> None:
    """A record that places nothing is not an rsID the snapshot lacks (`@unreachable-not-absent`)."""
    data = tmp_path / "clinvar" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {"chrom": ["16"], "start": [23635706], "ref": ["G"], "alt": [None], "rsid": ["rs1555461597"]},
        schema={"chrom": pl.Utf8, "start": pl.Int64, "ref": pl.Utf8, "alt": pl.Utf8, "rsid": pl.Utf8},
    ).write_parquet(data / "clinvar-null.parquet")
    warnings: list[str] = []
    con = clinvar._connect(tmp_path / "clinvar")
    try:
        loci = clinvar._lookup_positions_by_rsid(con, ["rs1555461597", "rs1"], warnings)
    finally:
        con.close()
    assert loci == {}
    assert [w.split(":")[0] for w in warnings] == ["rs1"]


@pytest.mark.parametrize("name", sorted(READERS))
def test_every_reader_spells_its_alleles_through_the_one_helper(name: str) -> None:
    module, function = name.split(".")
    assert {"per_alt_loci", "trim_allele"} & _calls(module, function), name


def test_no_snapshot_sql_aggregates_alt() -> None:
    """Grouping `alt` in SQL is the defect's shape: the group key is the padded ref the trim has to see."""
    for path in sorted(ENRICHER_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "string_agg(DISTINCT alt" not in text and "string_agg(alt" not in text, path.name


def test_the_trim_is_vcf_parsimony_and_needs_no_reference() -> None:
    """One ALT against a padded ref: shared trailing bases first, then leading ones, one anchor kept."""
    assert alleles.trim_allele(23635706, "GTT", "GT") == (23635706, "GT", "G")
    assert alleles.trim_allele(23635706, "GTT", "GTTT") == (23635706, "G", "GT")
    assert alleles.trim_allele(23635706, "GTT", "G") == (23635706, "GTT", "G")
    # A shared leading base past the anchor moves the start, as `bcftools norm` does.
    assert alleles.trim_allele(29608, "TC", "TTG") == (29609, "C", "TG")
    # Not bases: nothing to trim, handed back as given.
    assert alleles.trim_allele(5, "TA", "<DEL>") == (5, "TA", "<DEL>")
