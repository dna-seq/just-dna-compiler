"""Every drafting provider must read the build the module declares (D2).

`enrich.spec_genome_build` was written for the release where "the guard existed; the value never
arrived", and then had **exactly one caller** — `enrich()`. `draft`, `draft-panel` and `draft-clinpgx`
all take a `spec_dir`, all sit next to `module_spec.yaml`, and none of them asked. Every source they
read is GRCh38, so drafting CYP2C9 into a `genome_build: GRCh37` module wrote `10,94942290` for
`rs1799853` — whose GRCh37 position is `96702047` — in silence, and no downstream check can catch it:
a coordinate is valid on either assembly, it is simply a different base.

**Why it hid is the point of this file.** `test_pgx_draft.py`'s fixture yaml says
`genome_build: GRCh38`, and it is the only drafting test that mentions a build at all — so the whole
suite could not distinguish "reads the module's build" from "assumes GRCh38", which is the corpus
uniformity that let `reverse_module` hardcode the same constant for a release. The fixtures below
declare **GRCh37**, and the assertion is on the warning naming both builds.

The provider still writes the row. Refusing would make three commands unusable on a non-GRCh38
module, and silently dropping the coordinate produces a different row than the author asked for —
both are design decisions, and the enricher reports rather than repairs.
"""

import csv
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.clinvar_draft import CLINVAR_GENOME_BUILD
from just_dna_enricher.cpic import CpicClient
from just_dna_enricher.enrich import source_build_mismatch
from just_dna_enricher.pgx_draft import CPIC_GENOME_BUILD, draft_gene

# Trimmed CPIC PostgREST payloads — self-contained rather than imported from `test_pgx_draft`, which
# is the file's own convention here (no test module imports another). One gene, two alleles, one
# defining variant carrying a coordinate, which is all this file needs: the row that would be written
# on the wrong assembly.
_GENES = [{"symbol": "CYP2C19", "chr": "chr10"}]
_ALLELES = [
    {"genesymbol": "CYP2C19", "name": "*1", "activityvalue": "1.0",
     "clinicalfunctionalstatus": "Normal function"},
    {"genesymbol": "CYP2C19", "name": "*2", "activityvalue": "0.0",
     "clinicalfunctionalstatus": "No function"},
]
_DIPLOTYPES = [
    {"genesymbol": "CYP2C19", "diplotype": "*1/*2", "generesult": "Intermediate Metabolizer",
     "totalactivityscore": "1.0"},
]
_DEFINITIONS = [{"id": 1, "genesymbol": "CYP2C19", "name": "*2"}]
#: **The key is `sequence_location`, and it was `location` until R2-3.** `cpic.defining_variants`
#: reads `r.get("sequence_location")` — the same name its PostgREST `select` asks for — so the nested
#: dict was always `{}` and every claim this file makes about "one defining variant carrying a
#: coordinate" was hollow: the drafted haplotype row had no position, and the file passed either way.
#: Third instance of the class after S21's registry and D6-2's `_MOVABLE` — a guard proving less than
#: its name says. `test_the_cpic_provider_warns_and_still_drafts` now asserts the coordinate reaches
#: `haplotypes.csv`, which is what makes the key matter.
_LOCATIONS = [
    {"alleledefinitionid": 1, "variantallele": "A",
     "sequence_location": {"chromosomelocation": "NC_000010.11:g.94781859G>A",
                           "position": 94781859, "dbsnpid": "rs4244285",
                           "genesymbol": "CYP2C19"}},
]


def _client() -> CpicClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/gene"):
            return httpx.Response(200, json=_GENES)
        if path.endswith("/allele"):
            return httpx.Response(200, json=_ALLELES)
        if path.endswith("/diplotype"):
            return httpx.Response(200, json=_DIPLOTYPES)
        if path.endswith("/allele_definition"):
            return httpx.Response(200, json=_DEFINITIONS)
        if path.endswith("/allele_location_value"):
            return httpx.Response(200, json=_LOCATIONS)
        return httpx.Response(404, json=[])

    return CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def _spec(tmp_path: Path, build: str) -> Path:
    spec = tmp_path / build
    spec.mkdir(exist_ok=True)
    (spec / "module_spec.yaml").write_text(
        'schema_version: "1.0"\n'
        "module:\n  name: cyp2c9\n  title: T\n  report_title: T\n  description: d\n"
        f"genome_build: {build}\n"
    )
    return spec


@pytest.mark.parametrize("build", ["GRCh37", "GRCh36"])
def test_a_non_default_build_is_named_against_the_source(tmp_path: Path, build: str) -> None:
    """Both assemblies appear, because a message naming one of them is half a diagnosis."""
    warning = source_build_mismatch(_spec(tmp_path, build), "CPIC", CPIC_GENOME_BUILD)
    assert warning is not None
    assert build in warning and CPIC_GENOME_BUILD in warning


def test_the_agreeing_case_is_silent(tmp_path: Path) -> None:
    """"The builds agree" is not a finding, and a warning on every ordinary draft is noise."""
    assert source_build_mismatch(_spec(tmp_path, "GRCh38"), "CPIC", CPIC_GENOME_BUILD) is None
    assert (
        source_build_mismatch(_spec(tmp_path, "GRCh38"), "ClinVar", CLINVAR_GENOME_BUILD) is None
    )


def test_a_spec_with_no_yaml_is_the_default_build(tmp_path: Path) -> None:
    """A bare table directory compiles as GRCh38, so drafting into one is not a mismatch.

    `spec_genome_build` answers `GRCh38` there deliberately — it returns what compiling that
    directory would assume rather than guessing — and this pins that a provider does not start
    warning about a directory whose build nothing has stated.
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    assert source_build_mismatch(bare, "CPIC", CPIC_GENOME_BUILD) is None


def test_the_cpic_provider_warns_and_still_drafts(tmp_path: Path) -> None:
    """End to end through `draft_gene`: the warning is emitted and the rows are written anyway.

    Both halves matter. Without the first, the author is not told; without the second, the fix has
    quietly turned a warning into a refusal, which is a decision this round explicitly did not take.
    """
    spec = _spec(tmp_path, "GRCh37")
    result = draft_gene(spec, "CYP2C19", client=_client(), declared_use="non_commercial")

    mismatch = [w for w in result.warnings if "publishes GRCh38 coordinates" in w]
    assert len(mismatch) == 1, result.warnings
    assert "genome_build='GRCh37'" in mismatch[0]
    assert not result.skipped
    assert (spec / "allele_function.csv").is_file()

    # **The row the warning is about must actually exist** (R2-3). Without this the file asserted a
    # message and never checked that the coordinate the message warns about was written — and with
    # the fixture's location key misspelled, it was not. `94781859` is CPIC's GRCh38 position for
    # `rs4244285`; the point of the warning is that it lands in a module declaring GRCh37.
    haplotypes = list(csv.DictReader((spec / "haplotypes.csv").open()))
    starred = [r for r in haplotypes if r["allele"] == "A"]
    assert [(r["chrom"], r["start"], r["rsid"]) for r in starred] == [("10", "94781859", "rs4244285")]


def test_the_default_build_draft_is_unchanged(tmp_path: Path) -> None:
    """The GRCh38 path emits no build warning at all — the regression guard on the fix itself."""
    result = draft_gene(
        _spec(tmp_path, "GRCh38"), "CYP2C19", client=_client(), declared_use="non_commercial"
    )
    assert not [w for w in result.warnings if "coordinates and this module declares" in w]


def test_an_unreadable_spec_exits_cleanly_rather_than_tracebacking(tmp_path: Path) -> None:
    """The presentation half of the same repair (R2-2), and it regressed *because* F1 was fixed.

    `source_build_mismatch` raises `EnrichmentError` on a present-but-unreadable `module_spec.yaml`
    — correctly: a module whose declaration cannot be read has no build to draft against. But
    routing the providers through it gave two CLIs an exception their handlers did not name, so a
    spec carrying only `name:` (an ordinary mid-authoring state, not a corrupt file) turned
    `draft-panel` into a rich traceback where every other enricher command exits with a message.

    Both commands are checked, because the handlers were separately wrong and a shared tuple is what
    now keeps them together. `draft-panel` runs `--offline`: the raise must land before any snapshot
    is provisioned, so this passes with no cache on the machine.
    """
    from typer.testing import CliRunner

    from just_dna_enricher.cli import app

    spec = tmp_path / "half-authored"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text("name: broken\n")

    for argv in (
        ["draft-panel", str(spec), "--gene", "PALB2", "--offline"],
        ["draft", str(spec), "--gene", "CYP2C19", "--offline", "--use", "non_commercial"],
    ):
        result = CliRunner().invoke(app, argv)
        assert result.exit_code == 1, (argv, result.output)
        assert result.exception is None or isinstance(result.exception, SystemExit), argv
        assert "DRAFT FAILED" in result.output, (argv, result.output)
        assert "genome_build" in result.output, (argv, result.output)
