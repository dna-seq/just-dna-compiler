"""One rsID, two placement sets in one `resolution.csv` (RM374).

**The class.** `resolution.csv` is merge-not-clobber: a re-run fills the subjects it has no row for and
never re-asks the ones it has. So once the Ensembl snapshot moved release (RM372), a module enriched before
the move and again after it carries answers from both releases side by side, and nothing compared them.
The 0.8 migration probe's `Q_mixed` table is the instance this file is built from (its real rows):
`rs761191455` is placed at `13:48041104 G>GG` under its own key (the old release's right-shifted spelling)
and at `13:48041103 T>TG` under the positional key a later row was authored at (the new release's
left-aligned one). A consumer joining a left-aligned VCF by position matched one of them; validate, compile
and strict were silent.

**How the table tells one answer from two.** A `variant_key` is one subject, and a re-run replaces a
subject's rows whole (`ResolutionRow._KEY_RULE = "subject"`), so the rows under one key are one answer and
`locus_index` only orders its loci. Two answers about one rsID are two keys whose rows carry that rsID: the
rsID's own key (a full answer, every locus the source placed it at that the authored allele can sit on) and
a positional key whose rsID was back-filled (one locus, the one its row was authored at). Rows sharing a key
and a `locus_index` are NOT read as two answers: a hand-filled table leaves `locus_index` at its default 0
for every locus of a one-to-many rsID, so the table cannot tell that from two answers, and withholds.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.compiler.allele_checks import _check_allele_membership
from just_dna_compiler.compiler.parquets import (
    RESOLUTION_LOCUS_DTYPE,
    RESOLUTION_LOCUS_EXCLUDED,
    resolution_loci,
)
from just_dna_compiler.resolution import PLACEMENTS_DISAGREE_PHRASE, placement_disagreements
from just_dna_format.manifest import read_manifest
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import par_partner

CODE = "rsid_placements_disagree"
_PHRASE = PLACEMENTS_DISAGREE_PHRASE

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm374\n  title: RM374\n  description: one identity, one placement set\n"
    "  report_title: RM374\n"
    "genome_build: GRCh38\n"
)
_RES_HEADER = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
#: The probe's two rows for rs761191455, verbatim but for the provenance columns this check never reads.
_OLD = "rs761191455,rs761191455,13,48041104,G,GG,GRCh38,0,cache,ensembl,resolved\n"
_NEW = "13:48041103:T:TG,rs761191455,13,48041103,T,TG,GRCh38,0,cache,ensembl,resolved\n"
#: A real study of a real row, so the spec carries the grounding `validate` demands (from the probe spec).
_LPA = "rs10455872,rs10455872,6,160589086,A,G,GRCh38,0,cache,ensembl,resolved\n"
_STUDIES = "rsid,pmid\nrs10455872,32678081\n"
_VARIANTS = (
    "rsid,genotype,state,conclusion,chrom,start,ref,alts\n"
    "rs10455872,A/G,risk,one copy of the LPA G allele,,,,\n"
    "rs761191455,G/GG,risk,the NUDT15 insertion authored by rsID,,,,\n"
    ",T/TG,risk,the same insertion authored by position in the left-aligned spelling,13,48041103,T,TG\n"
)
#: The probe's whole `Q_mixed372/resolution.csv`, verbatim: old-release rows beside new ones.
_PROBE_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,caid,source,authority,status,rsid_alternates,rsid_current,rsid_status,placement_witness,placement_verdict,left_aligned,fetched_at\n"
    "13:48041103:T:TG,rs761191455,13,48041103,T,TG,GRCh38,0,,,,cache,ensembl,resolved,,,,,,,\n"
    "rs10455872,rs10455872,6,160589086,A,G,GRCh38,0,ga4gh:VA.p4HqyaoHIUA38oR8OAHepboYMGGti_mL,2.0,,cache,ensembl,resolved,,,,clinvar,same_event,true,\n"
    "rs1457579126,rs1457579126,13,48040978,AA,A,GRCh38,0,,,,cache,ensembl,resolved,,,,clinvar,unplaced,,\n"
    "rs2802292,rs2802292,6,108587315,G,T,GRCh38,0,ga4gh:VA.fpT7pxOvs4veTsG7gQcATmU5FexrdQV2,2.0,,cache,ensembl,resolved,,,,clinvar,same_event,true,\n"
    "rs429358,rs429358,19,44908684,T,C,GRCh38,0,ga4gh:VA.NsWfIPdbQ9LWo4Z5f9lIhMW87kZCtrEc,2.0,,cache,ensembl,resolved,,,,clinvar,same_event,true,\n"
    'rs4970836,rs4970836,1,109279175,G,"A,C",GRCh38,0,"ga4gh:VA.qkaXjTDKwuhvGj7DTzgNAamwJxUtC2yG,ga4gh:VA.S6YrBTxfDwxiDNWVUiYLvuWgC4lng5TO",2.0,,cache,ensembl,resolved,,,,clinvar,unplaced,true,\n'
    'rs646776,rs646776,1,109275908,C,"G,T",GRCh38,0,"ga4gh:VA.FFPVCtO58NakdrETYplBZDMrkVjO7poY,ga4gh:VA.HyXSjaqBtrrwEmmm7WiI6-4ldjuDX5UN",2.0,,cache,ensembl,resolved,,,,clinvar,unplaced,true,\n'
    'rs746071566,rs746071566,13,48037782,AGGAGTC,"A,AGGAGTCGGAGTC,AGGAGTCGGAGTCGGAGTC",GRCh38,0,,,,cache,ensembl,resolved,,,,clinvar,undecided,,\n'
    "rs75571981,rs75571981,6,63910997,T,C,GRCh38,0,ga4gh:VA.zgi4B721QJt7bFBVYgkugTs58mqTM8CE,2.0,,cache,ensembl,resolved,,,,clinvar,unplaced,true,\n"
    "rs761191455,rs761191455,13,48041104,G,GG,GRCh38,0,,,,cache,ensembl,resolved,,,,clinvar,unplaced,,\n"
)
#: The probe spec's authored identities and genotypes (its conclusions shortened).
_PROBE_VARIANTS = (
    "rsid,genotype,state,conclusion,chrom,start,ref,alts\n"
    "rs10455872,A/G,risk,c,,,,\n"
    "rs429358,C/T,risk,c,,,,\n"
    "rs646776,C/T,protective,c,,,,\n"
    "rs75571981,C/T,protective,c,,,,\n"
    "rs2802292,G/T,protective,c,,,,\n"
    "rs761191455,G/GG,risk,c,,,,\n"
    "rs1457579126,A/AA,risk,c,,,,\n"
    "rs746071566,A/AGGAGTC,risk,c,,,,\n"
    ",T/TG,risk,c,13,48041103,T,TG\n"
    "rs646776,A/C,risk,c,,,,\n"
)


def _spec(root: Path, resolution: str, variants: str = _VARIANTS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (root / "variants.csv").write_text(variants, encoding="utf-8")
    (root / "resolution.csv").write_text(resolution, encoding="utf-8")
    (root / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return root


def _row(
    key: str, rsid: str | None, chrom: str, start: int, ref: str, alts: str, **kw: object
) -> ResolutionRow:
    return ResolutionRow(
        variant_key=key, rsid=rsid, chrom=chrom, start=start, ref=ref, alts=alts, status="resolved", **kw
    )


# ── the probe's mixed table ───────────────────────────────────────────────────────────────────────


def test_the_mixed_table_refuses_a_strict_validate_and_compile(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _RES_HEADER + _LPA + _NEW + _OLD)
    validated = validate_spec(spec, strict=True)
    assert not validated.valid
    refusal = [e for e in validated.errors if "rs761191455" in e and _PHRASE in e]
    assert len(refusal) == 1, validated.errors
    compiled = compile_module(spec, tmp_path / "out", strict=True)
    assert not compiled.success
    assert compiled.errors == validated.errors
    assert not (tmp_path / "out").exists()


def test_best_effort_warns_once_naming_both_placements_and_the_remedy(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _RES_HEADER + _LPA + _NEW + _OLD)
    validated = validate_spec(spec)
    assert validated.valid, validated.errors
    assert validated.warnings_summary.get(CODE) == 1
    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    assert compiled.warnings_summary.get(CODE) == 1
    # A result's `warnings` are plain strings (pydantic flattens the code), so the sentence is found by
    # its pinned phrase and the code is read off `warnings_summary` above.
    (message,) = [w for w in compiled.warnings if _PHRASE in w]
    for fragment in (
        "rs761191455",
        "13:48041104 G>GG",
        "13:48041103 T>TG",
        "under 13:48041103:T:TG",
        "releases not recorded",
        "--rederive",
        "delete resolution.csv",
    ):
        assert fragment in message, (fragment, message)
    manifest = read_manifest(tmp_path / "out" / "manifest.json")
    assert manifest.compilation.warnings_summary.get(CODE) == 1


def test_the_finding_is_lap_stable(tmp_path: Path) -> None:
    """Both rows reach `weights.parquet` under their two keys, so reverse re-emits the disagreement: the
    second lap must say exactly what the first said (`@lap-stable-means-a-property-of-the-module`)."""
    spec = _spec(tmp_path / "spec", _RES_HEADER + _LPA + _NEW + _OLD)
    lap1 = compile_module(spec, tmp_path / "lap1")
    assert lap1.success, lap1.errors
    reverse_module(tmp_path / "lap1", tmp_path / "reversed")
    lap2 = compile_module(tmp_path / "reversed", tmp_path / "lap2")
    assert lap2.success, lap2.errors

    def said(result: object) -> list[str]:
        return [w for w in result.warnings if _PHRASE in w]

    assert said(lap1) and said(lap1) == said(lap2)


def test_a_fresh_table_is_silent(tmp_path: Path) -> None:
    """Delete-and-re-enrich (the probe's `Q_fresh`): both subjects answer `13:48041103 T>TG`."""
    fresh = _OLD.replace("48041104,G,GG", "48041103,T,TG")
    spec = _spec(tmp_path / "spec", _RES_HEADER + _LPA + _NEW + fresh)
    validated = validate_spec(spec, strict=True)
    assert CODE not in validated.warnings_summary
    assert not [e for e in validated.errors if _PHRASE in e], validated.errors


def test_the_probe_table_names_rs761191455_and_nothing_else(tmp_path: Path) -> None:
    """The real `Q_mixed372` table: one placement finding, and it is rs761191455 (rs1457579126 and
    rs646776 moved too, but each has one subject, so the table holds one answer for each)."""
    spec = _spec(tmp_path / "spec", _PROBE_RESOLUTION, _PROBE_VARIANTS)
    validated = validate_spec(spec)
    found = [w for w in validated.warnings if _PHRASE in w]
    assert len(found) == 1 and found[0].startswith("rs761191455:"), found


# ── one answer with several loci is not two answers (`@membership-union`) ─────────────────────────


def test_a_positional_answer_inside_the_rsids_own_answer_agrees() -> None:
    rows = [
        _row("rs1", "rs1", "1", 100, "A", "G", locus_index=0),
        _row("rs1", "rs1", "5", 900, "A", "G", locus_index=1),
        _row("1:100:A:G", "rs1", "1", 100, "A", "G"),
        _row("5:900:A:G", "rs1", "5", 900, "A", "G"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


def test_a_positional_answer_outside_the_rsids_own_answer_disagrees() -> None:
    rows = [
        _row("rs1", "rs1", "1", 100, "A", "G", locus_index=0),
        _row("rs1", "rs1", "5", 900, "A", "G", locus_index=1),
        _row("1:101:C:G", "rs1", "1", 101, "C", "G"),
    ]
    (finding,) = placement_disagreements(rows, "GRCh38")
    assert finding.warning.code == CODE
    assert "1:101 C>G" in finding.warning and "1:100 A>G" in finding.warning


def test_only_positional_answers_withhold() -> None:
    """Two coordinates both labelled rs1 and no rs1-keyed answer: a one-to-many rsID authored by position
    twice and one event in two spellings look the same, so the table cannot say which (withheld)."""
    rows = [_row("1:100:A:G", "rs1", "1", 100, "A", "G"), _row("1:101:C:G", "rs1", "1", 101, "C", "G")]
    assert placement_disagreements(rows, "GRCh38") == []


def test_one_key_with_a_repeated_locus_index_is_never_two_answers() -> None:
    """Two rows under one key at `locus_index` 0: a hand-filled one-to-many rsID or two answers merged
    under one key, and the table cannot tell which, so one key is never reported against itself. A
    positional answer inside either of its loci still agrees."""
    rows = [
        _row("rs1", "rs1", "1", 100, "A", "G"),
        _row("rs1", "rs1", "1", 101, "C", "G"),
        _row("1:101:C:G", "rs1", "1", 101, "C", "G"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


def test_two_spellings_the_enricher_judged_are_withheld() -> None:
    """One release, two spellings: the rsID's answer was filled left-aligned (`left_aligned=true`, RM270)
    and a positional row authored at the snapshot's own right-shifted spelling was judged not left-aligned
    (`false`) and back-filled. `--rederive` would rewrite the same table, so this is the spelling question,
    never a stale answer, and the check withholds."""
    rows = [
        _row("rs761191455", "rs761191455", "13", 48041103, "T", "TG", left_aligned=True),
        _row("13:48041104:G:GG", "rs761191455", "13", 48041104, "G", "GG", left_aligned=False),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


def test_a_row_with_no_start_is_not_an_answer() -> None:
    """A located row with `chrom` and no `start` places nothing; it must not compare as position 0."""
    rows = [
        _row("rs1", "rs1", "1", 100, "A", "G"),
        ResolutionRow(variant_key="rs1", rsid="rs1", chrom="1", start=None, status="resolved", locus_index=1),
        _row("1:100:A:G", "rs1", "1", 100, "A", "G"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []
    only_half = [
        ResolutionRow(variant_key="rs1", rsid="rs1", chrom="1", start=None, status="resolved"),
        _row("1:100:A:G", "rs1", "1", 100, "A", "G"),
    ]
    assert placement_disagreements(only_half, "GRCh38") == []


def test_a_pseudoautosomal_partner_is_the_same_place() -> None:
    x_start = 640_851
    partner = par_partner("X", x_start)
    assert partner is not None
    rows = [
        _row("rs9", "rs9", "X", x_start, "A", "G"),
        _row(f"{partner[0]}:{partner[1]}:A:G", "rs9", partner[0], partner[1], "A", "G"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


def test_a_row_on_another_build_and_an_ambiguous_pick_are_not_answers() -> None:
    rows = [
        _row("rs1", "rs1", "1", 100, "A", "G"),
        _row("1:200:A:G", "rs1", "1", 200, "A", "G", genome_build="GRCh37"),
        ResolutionRow(
            variant_key="1:300:A:G",
            rsid="rs1",
            chrom="1",
            start=300,
            ref="A",
            alts="G",
            status="ambiguous",
            rsid_alternates="rs1,rs2",
        ),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


def test_a_non_grch38_module_is_not_asked() -> None:
    rows = [_row("rs1", "rs1", "1", 100, "A", "G"), _row("1:101:C:G", "rs1", "1", 101, "C", "G")]
    assert placement_disagreements(rows, "GRCh37") == []


def test_the_pieces_of_one_split_are_one_answer() -> None:
    """RM270 respells a multi-ALT locus into pieces: same start, two refs, ONE subject (the RM376 case,
    `rs746071566` online). The pieces are one answer, and a positional row naming one of them agrees."""
    rows = [
        _row("rs746071566", "rs746071566", "13", 48037782, "AGGAGTC", "A", locus_index=0),
        _row("rs746071566", "rs746071566", "13", 48037782, "A", "AGGAGTC", locus_index=1),
        _row("13:48037782:A:AGGAGTC", "rs746071566", "13", 48037782, "A", "AGGAGTC"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


# ── RM387: the rsID's own key is the narrowed answer, `source_loci` the whole one ─────────────────────


def _sibling(source_loci: str | None) -> list[ResolutionRow]:
    """The audit's probe (`audit2-probe/sibling.py`): the hosting filter kept locus A under the rsID's key,
    and a positional row was authored at sibling locus B, its rsID back-filled from the same answer."""
    return [
        _row("rs123", "rs123", "1", 1000, "A", "G", source_loci=source_loci),
        _row("1:5000:C:T", "rs123", "1", 5000, "C", "T"),
    ]


def test_a_sibling_locus_the_source_placed_is_one_answer() -> None:
    assert placement_disagreements(_sibling("1:1000,1:5000"), "GRCh38") == []


def test_a_sibling_recorded_without_the_whole_answer_still_reads_as_two() -> None:
    """A table written before the column: the rows are the whole answer, as RM374 read them, so the stale
    case it was built for still fires, and `--rederive` (which writes the column) is what clears a sibling."""
    (finding,) = placement_disagreements(_sibling(None), "GRCh38")
    assert finding.warning.code == CODE


def test_a_locus_outside_the_whole_answer_is_still_two_placements() -> None:
    """The column widens the answer to what the source offered, never further."""
    (finding,) = placement_disagreements(_sibling("1:1000,1:6000"), "GRCh38")
    assert "1:5000" in finding.warning
    # The sentence names what it compared against, so the author sees why 1:6000 would pass.
    assert "the source offered 1:1000, 1:6000" in finding.warning


def test_a_pseudoautosomal_offer_is_read_as_its_x_partner() -> None:
    x_start = 640_851
    partner = par_partner("X", x_start)
    assert partner is not None
    rows = [
        _row("rs9", "rs9", "1", 100, "A", "G", source_loci=f"1:100,Y:{partner[1]}"),
        _row(f"X:{x_start}:A:G", "rs9", "X", x_start, "A", "G"),
    ]
    assert placement_disagreements(rows, "GRCh38") == []


_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


@pytest.mark.parametrize(
    "example",
    sorted(p.parent.name for p in _EXAMPLES.glob("*/resolution.csv")),
)
def test_no_reference_example_is_read_as_two_placements(example: str) -> None:
    """Every committed table: the check is silent, so it neither warns nor refuses a strict compile of
    any example. The split it must stay silent on is pinned on a copy of `shox_par1` below."""
    validated = validate_spec(_EXAMPLES / example)
    assert CODE not in validated.warnings_summary, [w for w in validated.warnings if _PHRASE in w]


#: `shox_par1`'s `rs1569493663` as the old Ensembl snapshot answered it: one multi-ALT locus split into
#: two pieces (RM270). The split snapshot answers it with one row (`CAG>C`), so since the 0.8
#: regeneration no committed example carries a split, and the walk above can no longer reach one.
_SHOX_SPLIT = (
    "rs1569493663,rs1569493663,X,634689,CAG,C,GRCh38,0,,,,cache,ensembl,resolved\n",
    "rs1569493663,rs1569493663,X,634689,C,CAG,GRCh38,1,,,,cache,ensembl,resolved\n",
)


def test_a_real_module_carrying_a_split_is_silent(tmp_path: Path) -> None:
    """The walk above is only as good as its corpus, and the corpus lost its split when the examples
    were regenerated against the split snapshot. So the split is put back into a copy of the real
    `shox_par1`, and the same check must stay silent on it."""
    spec = tmp_path / "shox_par1"
    shutil.copytree(_EXAMPLES / "shox_par1", spec)
    path = spec / "resolution.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [row for row in rows if not row.startswith("rs1569493663,")]
    assert len(kept) == len(rows) - 1, "shox_par1 no longer carries rs1569493663"
    fields = header.rstrip("\n").split(",")
    pad = "," * (len(fields) - _SHOX_SPLIT[0].count(",") - 1)
    path.write_text(header + "".join(kept) + "".join(r.rstrip("\n") + pad + "\n" for r in _SHOX_SPLIT))
    validated = validate_spec(spec)
    assert validated.valid, validated.errors
    assert CODE not in validated.warnings_summary, [w for w in validated.warnings if _PHRASE in w]


# ── the releases, when the rows record them (RM373's column) ──────────────────────────────────────

_HAS_RELEASE = "source_release" in ResolutionRow.model_fields


@pytest.mark.skipif(not _HAS_RELEASE, reason="ResolutionRow.source_release (RM373) is not on this branch")
def test_the_message_names_each_answers_release_when_recorded() -> None:
    rows = [
        _row("rs761191455", "rs761191455", "13", 48041104, "G", "GG", source_release="ensembl-old"),
        _row("13:48041103:T:TG", "rs761191455", "13", 48041103, "T", "TG", source_release="ensembl-new"),
    ]
    (finding,) = placement_disagreements(rows, "GRCh38")
    assert "ensembl-old" in finding.warning and "ensembl-new" in finding.warning
    assert "releases not recorded" not in finding.warning


# ── item 4: a stale allele set says it may be stale ───────────────────────────────────────────────


def _membership_case() -> tuple[list[VariantRow], dict[str, list[ResolutionRow]]]:
    """The probe's `rs646776`: dbSNP 157 lists A, the old release's row (C>G,T) does not."""
    variants = [VariantRow(rsid="rs646776", genotype="A/C", state="risk", conclusion="probe")]
    table = {"rs646776": [_row("rs646776", "rs646776", "1", 109275908, "C", "G,T", authority="ensembl")]}
    return variants, table


def test_a_hand_filled_allele_set_gets_no_snapshot_reading() -> None:
    """A table row no external source answered (`authority` empty: authored, manual, reversed) came from no
    snapshot, so the stale-release reading and its remedy would be noise there."""
    variants, _ = _membership_case()
    table = {"rs646776": [_row("rs646776", "rs646776", "1", 109275908, "C", "G,T", source="manual")]}
    errors, _ = _check_allele_membership(variants, table, strict=True)
    (error,) = errors
    assert "earlier snapshot release" not in error and "--rederive" not in error


def test_a_resolved_allele_refusal_names_the_stale_reading_and_the_remedy() -> None:
    variants, table = _membership_case()
    errors, _ = _check_allele_membership(variants, table, strict=True)
    (error,) = errors
    assert "earlier snapshot release" in error and "--rederive" in error
    assert "release not recorded" in error


@pytest.mark.skipif(not _HAS_RELEASE, reason="ResolutionRow.source_release (RM373) is not on this branch")
def test_a_resolved_allele_refusal_names_the_rows_release() -> None:
    variants, _ = _membership_case()
    table = {
        "rs646776": [
            _row(
                "rs646776",
                "rs646776",
                "1",
                109275908,
                "C",
                "G,T",
                authority="ensembl",
                source_release="ensembl-old",
            )
        ]
    }
    errors, _ = _check_allele_membership(variants, table, strict=True)
    (error,) = errors
    assert "ensembl-old" in error


def test_the_whole_probe_spec_refuses_on_both_findings(tmp_path: Path) -> None:
    """The probe's spec under `--strict`: the placement finding beside the membership one it was confused with."""
    spec = _spec(tmp_path / "spec", _PROBE_RESOLUTION, _PROBE_VARIANTS)
    validated = validate_spec(spec, strict=True)
    joined = "\n".join(validated.errors)
    assert "rs761191455" in joined and _PHRASE in joined
    assert "rs646776" in joined and "--rederive" in joined


# ── RM387's carrier: a recorded column the compile reads must ride the round trip ──────────────────────


def test_every_resolution_column_is_carried_or_declared_uncarried() -> None:
    """An equality over the model's fields: a new column lands in the struct (and so in `reverse`) or in
    `RESOLUTION_LOCUS_EXCLUDED` with a reason, never silently in neither, which is how lap 2 loses what
    lap 1 read. Since RM380 the struct is derived from the model, so the RM387 half is that `source_loci`,
    which the compile's placement check reads, is carried and never excluded."""

    carried = {field.name for field in RESOLUTION_LOCUS_DTYPE.fields}
    assert carried == set(ResolutionRow.model_fields) - set(RESOLUTION_LOCUS_EXCLUDED)
    assert "source_loci" in carried
    row = _row("rs1", "rs1", "1", 100, "A", "G", source_loci="1:100,1:200")
    (locus,) = resolution_loci("rs1", {"rs1": [row]}, "GRCh38") or []
    assert set(locus) == carried
