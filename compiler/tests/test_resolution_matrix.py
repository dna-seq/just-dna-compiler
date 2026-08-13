"""The resolution round-trip contract, enumerated.

Resolution is where authored data meets injected facts, and the ways the two can disagree are a
*finite* set: five identity columns (`rsid`, `chrom`, `start`, `ref`, `alts`) the author may or may
not supply, crossed with what the table says about them. This file enumerates that set and pins one
rule over all of it:

> **Every combination is either round-trip stable on all three signatures, or it fails in `strict`.**

`best_effort` may carry an imperfect module and say so; `strict` promises a *reproducible* artifact, so
anything that cannot be reproduced from the injected table must not compile under it. `ambiguous` is
the single deliberate exception in the other direction — it *is* stable (the enricher writes one row
with the deterministic pick, and the candidate list is provenance), but it rests on a guessed label, so
it is best-effort-with-warning only.

The three signatures answer three different questions and all must hold:
  * `artifact.digest` — are the compiled bytes the same?
  * `content_signature` — is it still the same *authored* module? (this is the one that broke: reverse
    used to materialize resolved coordinates into `variants.csv`)
  * `resolution_signature` — do the resolved facts survive being written back out?
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module
from just_dna_format.base import derive_variant_key

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: D\n  description: d\n  report_title: D\n"
)
_RES_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,"
    "rsid_alternates,fetched_at\n"
)
_VAR_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"

# Authored identities the fixtures below key on. Derived, never pasted: a coord+alt substitution keys
# on its VRS allele id since 0.5, so a hand-written `7:700:C:G` would silently fail to join.
_KEY_COORD_ALT = derive_variant_key(None, "7", 700, "C", "G")
_KEY_COORD_ONLY = derive_variant_key(None, "7", 700, "C")


def _row(key, rsid, chrom, start, ref, alts, idx=0, status="resolved", alternates="") -> str:
    cell = f'"{alternates}"' if alternates else ""
    return (f"{key},{rsid},{chrom},{start},{ref},{alts},GRCh38,{idx},manual,{status},"
            f"{cell},\n")


_PHARM_HEADER = "rsid,chrom,start,ref,gene,genotype,drug,conclusion\n"


@dataclass(frozen=True)
class Case:
    label: str
    variants: str
    resolution: str
    #: True when compile -> reverse -> compile must reproduce all three signatures — except on a
    #: `table_says_more` case, where `resolution_signature` is expected to move and the other two
    #: still may not.
    stable: bool
    #: True when `strict` must refuse. The contract: `not stable` implies this.
    strict_refuses: bool
    #: `pharm_variants.csv` rows, for the positional half of the matrix (RM43). Since 0.6 the
    #: injected table is joined onto the positional 0.4 kinds too, so the same authored-shape ×
    #: mishap grid applies to them — and a table-only module (`variants=""`) is the shape that
    #: motivated the item, since it carries no `weights.parquet` for reverse to rebuild from.
    pharm: str = ""
    #: The injected table carries a fact this module never uses, so `resolution_signature` cannot
    #: survive the round trip — and no strict refusal follows, because nothing about the module is
    #: wrong.
    #:
    #: This is a THIRD axis beside authored-shape and mishap, and it was invisible until 0.6 stamped
    #: the signature for table-only modules: the grid had no case where the table says more than the
    #: module consumes. It is **not** a positional phenomenon, which the first entry below pins on a
    #: plain SNP module — `reverse_module` rebuilds the table from the artifact, so a row about a
    #: variant the module does not contain has nowhere to come from, exactly as `rsid_alternates` has
    #: nowhere to come from. Facts the artifact holds survive; facts it never held do not.
    #:
    #: Distinct from `stable=False`, and the distinction is the whole reason for a separate flag: an
    #: unstable case is one where the module's own resolution could not be reproduced, and `strict`
    #: must refuse it. Here the artifact is byte-identical on recompile (pinned separately by
    #: `test_artifact_digest_never_moves`) and only the provenance record of the injected table
    #: differs, so a refusal would be refusing a module for something its own bytes do not say.
    table_says_more: bool = False


CASES: list[Case] = [
    # ── the four authored shapes, cleanly resolved: all stable, all compile in strict ──────────
    Case("rsid-only, 1:1 fill",
         "rs777,,,,,C/G,risk,c\n",
         _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False),
    Case("rsid-only, one-to-many expansion (both loci can host the genotype)",
         "rs999,,,,,C/G,risk,c\n",
         _row("rs999", "rs999", 5, 500, "C", "G", 0)
         + _row("rs999", "rs999", 6, 600, "C", "G", 1),
         stable=True, strict_refuses=False),
    Case("coord+alt authored, rsid resolved",
         ",7,700,C,G,C/G,risk,c\n",
         _row(_KEY_COORD_ALT, "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False),
    Case("coord-only authored (no alt), rsid and alt resolved",
         ",7,700,C,,C/G,risk,c\n",
         _row(_KEY_COORD_ONLY, "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False),
    Case("pair authored (rsid + coord + alt), table agrees",
         "rs777,7,700,C,G,C/G,risk,c\n",
         _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False),

    # ── the indel row (RM31): the table spells one event differently from the genotype ─────────
    # ClinVar drafts `X:634689 CAG>C`, so the author writes `C/CAG`; Ensembl publishes the same 2 bp AG
    # deletion as `X:634690 AGAG>AG`. Both loci reconcile, so the expansion is complete and the whole
    # cycle is a fixed point — where before this pair produced no usable locus at all.
    Case("rsid-only indel, table carries the other published spelling",
         "rs1569493663,,,,,C/CAG,risk,c\n",
         _row("rs1569493663", "rs1569493663", "X", 634690, "AGAG", "AG", 0)
         + _row("rs1569493663", "rs1569493663", "Y", 634690, "AGAG", "AG", 1),
         stable=True, strict_refuses=False),
    # The same deletion written one base further right (the reference reads `C A G A G` from 634689, so
    # `634691 GAG>G` is that AG deletion again) reduces to the event `GA` where the genotype's reduces to
    # `AG`: same size, different content, which is what a repeat-region disagreement looks like and what
    # string algebra cannot settle. So the locus is KEPT — nothing is dropped, nothing is unreproducible,
    # `strict` has no complaint — and the compile says out loud that it did not decide.
    Case("rsid-only indel, spelling the tier cannot reconcile (kept, reported)",
         "rs1569493663,,,,,C/CAG,risk,c\n",
         _row("rs1569493663", "rs1569493663", "X", 634691, "GAG", "G", 0)
         + _row("rs1569493663", "rs1569493663", "Y", 634691, "GAG", "G", 1),
         stable=True, strict_refuses=False),
    # And the decidable negative still drops the locus, so this stays unstable + strict-refusing: the
    # event sizes differ (1 bp inserted vs 2 bp deleted), which re-anchoring cannot change.
    Case("expansion drops a locus whose indel is a different size",
         "rs281864532,,,,,G/GT,risk,c\n",
         _row("rs281864532", "rs281864532", 11, 5226675, "G", "GT", 0)
         + _row("rs281864532", "rs281864532", 11, 5226676, "GTT", "G", 1),
         stable=False, strict_refuses=True),

    # ── stable, but resting on something strict will not build on ─────────────────────────────
    Case("ambiguous: several rsIDs for one allele, deterministic pick recorded",
         ",7,700,C,G,C/G,risk,c\n",
         _row(_KEY_COORD_ALT, "rs777", 7, 700, "C", "G", status="ambiguous",
              alternates="rs777,rs888"),
         stable=True, strict_refuses=True),

    # ── unstable: the table cannot be reproduced from the artifact, so strict must refuse ──────
    Case("expansion drops a locus that cannot host the genotype",
         "rs999,,,,,C/G,risk,c\n",
         _row("rs999", "rs999", 5, 500, "C", "G", 0)
         + _row("rs999", "rs999", 6, 600, "A", "T", 1),
         stable=False, strict_refuses=True),
    Case("not_found: the table records the rsid as genuinely absent",
         "rs777,,,,,C/G,risk,c\n",
         _row("rs777", "", "", "", "", "", status="not_found"),
         stable=False, strict_refuses=True),
    Case("authored ref contradicts the table",
         "rs777,7,700,A,G,C/G,risk,c\n",
         _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=False, strict_refuses=True),
    Case("authored coordinate contradicts the table",
         "rs777,7,700,C,G,C/G,risk,c\n",
         _row("rs777", "rs777", 9, 900, "C", "G"),
         stable=False, strict_refuses=True),

    # ── nothing to resolve from ────────────────────────────────────────────────────────────────
    Case("no resolution row at all: the rsid stays unresolved",
         "rs777,,,,,C/G,risk,c\n",
         "",
         stable=True, strict_refuses=True),
    # Unstable for the same reason `not_found` is: an unresolved row has no coordinate, so reverse
    # writes no resolution row for it and the table's two candidates are gone.
    Case("every candidate locus contradicts the genotype: left unresolved",
         "rs999,,,,,A/T,risk,c\n",
         _row("rs999", "rs999", 5, 500, "C", "G", 0)
         + _row("rs999", "rs999", 6, 600, "C", "G", 1),
         stable=False, strict_refuses=True),

    # ── the table says more than the module uses: the injected row has nowhere to come back from ──
    # Pinned on the SNP core, where it originates and where it has always been true, rather than only
    # on the positional cases below where 0.6 first made it visible. `strict` accepts this module and
    # `artifact.digest` is reproducible; what cannot be reproduced is a row about a variant this
    # module does not contain, because reverse rebuilds the table from the artifact and the artifact
    # never held it.
    Case("the table carries a row about a variant the module does not have",
         "rs777,,,,,C/G,risk,c\n",
         _row("rs777", "rs777", 7, 700, "C", "G") + _row("rs111", "rs111", 8, 800, "A", "T"),
         stable=True, strict_refuses=False, table_says_more=True),

    # ── the positional 0.4 kinds (RM43). Same grid, no `variants.csv`: the module the item is about
    #    carries no `weights.parquet` at all, so reverse has to rebuild `resolution.csv` from the
    #    positional parquet or the recompile silently loses every coordinate. ────────────────────
    Case("table-only, rsid-authored pharm row, 1:1 fill",
         "", _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False,
         pharm="rs777,,,,SLCO1B1,C/G,simvastatin,c\n"),
    Case("table-only, rsid-authored pharm row, nothing in the table",
         "", _row("rs111", "rs111", 7, 700, "C", "G"),
         stable=True, strict_refuses=False, table_says_more=True,
         pharm="rs777,,,,SLCO1B1,C/G,simvastatin,c\n"),
    Case("table-only, coordinate-authored pharm row, rsid resolved",
         "", _row(_KEY_COORD_ONLY, "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False,
         pharm=",7,700,C,SLCO1B1,C/G,simvastatin,c\n"),
    Case("table-only, one-to-many rsid: left unplaced, never picked or expanded",
         "",
         _row("rs999", "rs999", 5, 500, "C", "G", 0)
         + _row("rs999", "rs999", 6, 600, "C", "G", 1),
         stable=True, strict_refuses=False, table_says_more=True,
         pharm="rs999,,,,SLCO1B1,C/G,simvastatin,c\n"),
    Case("table-only, half coordinate the table contradicts: left exactly as authored",
         "", _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False, table_says_more=True,
         pharm="rs777,,999,,SLCO1B1,C/G,simvastatin,c\n"),
    Case("pharm row beside the SNP core on one key: weights own the fact",
         "rs777,,,,,C/G,risk,c\n", _row("rs777", "rs777", 7, 700, "C", "G"),
         stable=True, strict_refuses=False,
         pharm="rs777,,,,SLCO1B1,C/G,simvastatin,c\n"),
]


def _spec(root: Path, case: Case) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    # `variants.csv` is optional (RM2 composition), and `studies.csv` is mandatory iff it is present —
    # so a positional-only case writes neither, which is exactly the module shape RM43 is about.
    if case.variants:
        (spec / "variants.csv").write_text(_VAR_HEADER + case.variants)
        (spec / "studies.csv").write_text("rsid,pmid\nrs777,29165669\nrs999,29165669\n")
    if case.pharm:
        (spec / "pharm_variants.csv").write_text(_PHARM_HEADER + case.pharm)
    (spec / "resolution.csv").write_text(_RES_HEADER + case.resolution)
    return spec


def _signatures(spec: Path, out: Path):
    result = compile_module(spec, out)
    assert result.success, result.errors
    return (
        result.manifest.artifact.digest,
        content_signature(spec),
        result.manifest.compilation.resolution_signature,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_resolution_round_trip_contract(case: Case) -> None:
    """`best_effort` always compiles; stability and the strict verdict follow the declared contract."""
    root = Path(tempfile.mkdtemp())
    spec = _spec(root, case)

    before = _signatures(spec, root / "o1")
    reverse_module(root / "o1", root / "rev")
    after = _signatures(root / "rev", root / "o2")

    names = ("artifact.digest", "content_signature", "resolution_signature")
    moved = [n for n, a, b in zip(names, before, after, strict=True) if a != b]
    if case.table_says_more:
        # The EXACT mover set, not "something may move": the exemption is only ever about the
        # injected table's own provenance hash, so a digest or content-signature movement on one of
        # these still fails here rather than hiding behind the flag.
        assert moved == ["resolution_signature"], (
            f"{case.label}: only resolution_signature may move when the table says more than the "
            f"module uses, but {moved} moved"
        )
    elif case.stable:
        assert not moved, f"{case.label}: expected a fixed point, but {moved} moved"
    else:
        assert moved, f"{case.label}: declared unstable but nothing moved — update the contract"

    strict = compile_module(spec, root / "o_strict", strict=True)
    assert strict.success is not case.strict_refuses, (
        f"{case.label}: strict should {'refuse' if case.strict_refuses else 'accept'}; "
        f"errors={strict.errors}"
    )


def test_the_contract_itself_holds() -> None:
    """The rule this file exists to enforce: instability always implies a strict refusal.

    Asserted over the table rather than per-case so a future entry cannot quietly declare itself
    unstable *and* strict-clean — which is the exact hole that let a non-reproducible artifact compile.
    """
    violations = [c.label for c in CASES if not c.stable and not c.strict_refuses]
    assert not violations, f"unstable but accepted by strict: {violations}"


def test_artifact_digest_never_moves() -> None:
    """The strongest of the three, and it must hold even where the other two legitimately cannot.

    A module that compiles at all must compile to the same bytes twice, whatever the authoring mishap —
    otherwise a published digest could not be re-derived by anyone.
    """
    for case in CASES:
        root = Path(tempfile.mkdtemp())
        spec = _spec(root, case)
        first = _signatures(spec, root / "o1")
        reverse_module(root / "o1", root / "rev")
        second = _signatures(root / "rev", root / "o2")
        assert first[0] == second[0], f"{case.label}: artifact.digest moved"
