"""RM394: every case the `--rederive` migration reports has its own sentence, and each names its remedy.

Audit round 3 and the 0.8 docs pass found three reports with fewer arms than the cases they describe:
the drift label called an allele the source added "moved: the source names a different event" (94
subjects across the reference examples), the derived-layer currency line sent an operator whose local
snapshot was the old release to `--rederive`, which repeats the line, and the carry-forward said "no
source could be asked" about subjects a link had answered. `rederive_words` holds each report as a closed
set of cases and a map to its sentence; these tests walk every case.

`@answered-is-not-absent` (a verdict with several arms owes a reason with the same arms, pairwise
distinct) and `@warning-text-is-api` (the phrases are pinned here).
"""

import ast
import csv
import logging
import shutil
from itertools import combinations
from pathlib import Path

import pytest
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.outcome import SubjectDrift, _drift_case
from just_dna_enricher.enrich.rederive_words import (
    CARRY_REASONS,
    CARRY_SENTENCES,
    CURRENCY_CASES,
    CURRENCY_REMEDIES,
    DRIFT_CASES,
    DRIFT_PHRASES,
    RESPELLED_BY_CASE,
    currency_case,
    currency_remedy,
)
from just_dna_enricher.events import no_mint
from just_dna_format.resolution import ResolutionRow

_ROOT = Path(__file__).parents[2]
_ORCHESTRATION = _ROOT / "enricher" / "src" / "just_dna_enricher" / "enrich" / "orchestration.py"


def _distinct(sentences: dict[str, str]) -> None:
    for (a, x), (b, y) in combinations(sentences.items(), 2):
        assert x != y and x not in y and y not in x, f"{a} and {b} say the same thing"


# ── the drift label ──────────────────────────────────────────────────────────────────────────────


def _row(alts: str, *, rsid: str | None = "rs1", start: int = 100, ref: str = "G", build: str = "GRCh38"):
    return ResolutionRow(
        variant_key="rs1", rsid=rsid, chrom="1", start=start, ref=ref, alts=alts, genome_build=build
    )


#: One real pair of rows per case, judged by the function the run calls. Offline: no ids, no reference.
_DRIFT_EXAMPLES: dict[str, tuple[list[ResolutionRow], list[ResolutionRow]]] = {
    "respelled": ([_row("GT", ref="GA")], [_row("T", ref="A", start=101)]),
    "gained_allele": ([_row("A")], [_row("A,T")]),
    "lost_allele": ([_row("A,T")], [_row("A")]),
    "gained_rsid": ([_row("A", rsid=None)], [_row("A")]),
    "renamed": ([_row("A")], [_row("A", rsid="rs2")]),
    "moved": ([_row("A")], [_row("A", start=200)]),
    "undecided": ([_row("A", ref="AG")], [_row("A,AGG", ref="AG")]),
}


def test_every_drift_case_has_one_phrase_and_a_respelled_value() -> None:
    assert set(DRIFT_PHRASES) == DRIFT_CASES
    assert set(RESPELLED_BY_CASE) == DRIFT_CASES
    _distinct(DRIFT_PHRASES)


@pytest.mark.parametrize("case", sorted(DRIFT_CASES))
def test_every_drift_case_is_what_the_judge_answers_for_its_example(case: str) -> None:
    before, after = _DRIFT_EXAMPLES[case]
    assert _drift_case(before, after, mint=no_mint, read_window=None) == case
    drift = SubjectDrift("rs1", "a", "b", RESPELLED_BY_CASE[case], case)
    assert str(drift).endswith(f"({DRIFT_PHRASES[case]})")


def test_the_examples_cover_the_registry() -> None:
    assert set(_DRIFT_EXAMPLES) == DRIFT_CASES


def test_an_allele_the_source_added_is_never_called_moved() -> None:
    """The audit's case: A → A,T was "moved: the source names a different event"."""
    before, after = _DRIFT_EXAMPLES["gained_allele"]
    text = str(SubjectDrift("rs1", "a", "b", False, _drift_case(before, after)))
    assert "gained an allele" in text and "moved" not in text


def test_a_case_that_contradicts_respelled_is_refused_and_an_older_call_keeps_its_arm() -> None:
    with pytest.raises(ValueError):
        SubjectDrift("rs1", "a", "b", True, "moved")
    assert [SubjectDrift("rs1", "a", "b", r).case for r in (True, False, None)] == [
        "respelled",
        "moved",
        "undecided",
    ]


# ── the carry-forward ────────────────────────────────────────────────────────────────────────────

#: The remedy each reason must name: written here, apart from the sentence, so the two are compared.
_CARRY_REMEDY = {
    "not_asked": "without --offline",
    "off_build": "until the module moves build",
    "no_reverse_map": "cache pull --only ensembl",
    "unreachable": "re-run when the link answers",
    "rejected": "check the genotype",
    "not_re_answered": "re-run to re-ask them",
}


def test_every_carry_reason_has_one_sentence_naming_its_remedy() -> None:
    assert set(CARRY_SENTENCES) == CARRY_REASONS == set(_CARRY_REMEDY)
    _distinct(CARRY_SENTENCES)
    for reason, remedy in _CARRY_REMEDY.items():
        assert remedy in CARRY_SENTENCES[reason], reason
    # Only the reason for subjects nobody could ask says so.
    asked = [r for r in CARRY_REASONS if r not in {"not_asked", "off_build"}]
    assert all("no source could be asked" not in CARRY_SENTENCES[r] for r in asked)


def test_the_run_declares_every_carry_reason_and_defaults_only_to_the_one_that_claims_none() -> None:
    """An AST walk over the run: the reasons the branches write into `no_row_reason` are the registry
    less `not_re_answered`, which is only ever the carry-forward's default."""
    tree = ast.parse(_ORCHESTRATION.read_text(encoding="utf-8"))
    declared: set[str] = set()
    defaults: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Subscript) and getattr(t.value, "id", None) == "no_row_reason"
            for t in node.targets
        ):
            # The values written, never a constant a condition compares against (`genome_build == "GRCh38"`).
            compared = {
                id(c) for t in ast.walk(node.value) if isinstance(t, ast.Compare) for c in ast.walk(t)
            }
            declared |= {
                c.value
                for c in ast.walk(node.value)
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and id(c) not in compared
            }
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", None) == "get"
            and getattr(node.func.value, "id", None) == "no_row_reason"
        ):
            defaults |= {a.value for a in node.args[1:] if isinstance(a, ast.Constant)}
    assert declared == CARRY_REASONS - {"not_re_answered"}
    assert defaults == {"not_re_answered"}


_HFE = _ROOT / "reference_examples" / "hfe_hemochromatosis"


@pytest.mark.usefixtures("no_ambient_caches")
def test_a_rederive_with_no_snapshot_names_each_carried_group_by_its_reason(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The audit's run: hfe offline with every cache empty. Its rsID subjects were asked of nothing, and its
    two coordinate-only subjects had no position→rsID map; one line names both groups apart."""
    spec = tmp_path / "hfe"
    shutil.copytree(_HFE, spec)
    with (spec / "resolution.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    positional = sorted(r["variant_key"] for r in rows if r["variant_key"] != r["rsid"])
    nowhere = tmp_path / "nowhere"
    with caplog.at_level(logging.WARNING):
        enrich(
            spec,
            rederive=True,
            offline=True,
            download=False,
            ensembl_cache=nowhere,
            clinvar_cache=nowhere,
            clinvar_gkm_cache=nowhere,
            pubmind_cache=nowhere,
            civic_cache=nowhere,
            use_gnomad=False,
            verify_ref=False,
            verify_rsids=False,
            verify_clinsig=False,
            verify_datasets=False,
        )
    (line,) = [r.getMessage() for r in caplog.records if "kept the recorded rows" in r.getMessage()]
    assert f"{len(rows) - len(positional)} subject(s): {CARRY_SENTENCES['not_asked']}" in line
    assert f"{len(positional)} subject(s): {CARRY_SENTENCES['no_reverse_map']}" in line
    assert all(key[:20] in line.split(CARRY_SENTENCES["no_reverse_map"])[1] for key in positional)


# ── the derived-layer currency line ──────────────────────────────────────────────────────────────

#: For each case: what its sentence must name, and what it must not (a remedy that does not apply).
_CURRENCY_REMEDY = {
    "table_behind_snapshot": ("`enrich --rederive`", "cache pull"),
    "snapshot_behind": ("cache pull --only clinvar", "is current"),
    "both_behind": ("cache pull --only clinvar", "is current"),
    "snapshot_unread": ("cache status", "is current"),
}

#: `(recorded, current, local, comparable)` reaching each case.
_CURRENCY_EXAMPLES = {
    "table_behind_snapshot": ("clinvar_2026-06-27", "clinvar_2026-11-01", "clinvar_2026-11-01", True),
    "snapshot_behind": ("clinvar_2026-06-27", "clinvar_2026-11-01", "clinvar_2026-06-27", True),
    "both_behind": ("clinvar_2026-06-27", "clinvar_2026-11-01", "clinvar_2026-09-05", True),
    "snapshot_unread": ("clinvar_2026-06-27", "clinvar_2026-11-01", None, False),
}


def test_every_currency_case_has_one_remedy_and_the_right_one() -> None:
    assert set(CURRENCY_REMEDIES) == CURRENCY_CASES == set(_CURRENCY_REMEDY) == set(_CURRENCY_EXAMPLES)
    _distinct(CURRENCY_REMEDIES)
    for case, (named, absent) in _CURRENCY_REMEDY.items():
        text = currency_remedy(case, lane="clinvar", local="clinvar_2026-06-27")
        assert named in text and absent not in text, case
        assert "{" not in text, case
    # Only the case where the table alone is behind sends the operator to a re-derivation alone.
    for case in CURRENCY_CASES - {"table_behind_snapshot"}:
        assert "cache pull --only clinvar" in currency_remedy(case, lane="clinvar", local=None), case


@pytest.mark.parametrize("case", sorted(CURRENCY_CASES))
def test_every_currency_case_is_reached_by_its_example(case: str) -> None:
    assert currency_case(*_CURRENCY_EXAMPLES[case]) == case


def test_a_snapshot_label_in_another_form_is_unread_never_a_guessed_side() -> None:
    assert (
        currency_case("clinvar_2026-06-27", "clinvar_2026-11-01", "clinvar_sha256:" + "ab" * 32, False)
        == "snapshot_unread"
    )
