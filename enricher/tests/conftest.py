"""Shared fixtures for the enricher suite.

**One autouse fixture, and it exists for the failure mode that only shows up on a machine that has
done real work.** `lookup_variant` consults the PubMind snapshot since RM134 § D, and a caller that
passes no `pubmind_cache` falls through to `$JUST_DNA_PUBMIND_CACHE` and then to the default cache
directory. Every existing lookup test passes an explicit `ensembl_cache`/`clinvar_cache` and no
PubMind one, so on a developer's machine — where a snapshot exists precisely because somebody built
it while designing this — the hint would gain `pubmind` advisories that CI never sees, and
`test_the_live_locus_is_labelled_live_and_not_as_a_snapshot` asserts an *exact set* of advisory
sources. Passing alone and failing in the one place that matters is the shape `@test-no-credential`
names.

So the variable is pointed at a directory that does not exist, which is the ladder's own way of
saying "no snapshot": `_resolve_parquet_cache` takes the explicit value over the default directory,
and a path that is not a directory resolves to `None`. Set rather than deleted, for the same reason
that rule gives — a `delenv` leaves the *default* directory still in play, which is the other half of
the ladder and the half that actually holds a built snapshot. A test that wants a snapshot passes one
explicitly and is unaffected.

**A second autouse fixture blanks `HF_TOKEN`** (RM301), for the same reason one layer over: the
publisher's tests stub `get_token()`, and the repository's own `.env` must not outrank the stub.

**A third autouse fixture fences the real HuggingFace hub** (RM372). `_provision_snapshot` is the
one writer into a cache base, and it reaches the network through `huggingface_hub.HfFileSystem`
(the upload half's read through `hf_hub_download`). On 2026-11-04 `test_rebuild_caches_and_prepare_
caches_are_the_cli_loops` ran `prepare_caches` on the real Ensembl lane, the lane's new repo turned
the developer's recorded cache into a re-pull, and six chromosomes of the shared base were replaced
with another release while other sessions read it. So without `JUST_DNA_NETWORK_TESTS=1` both names
refuse, and a test that wants a hub installs its own fake over this one. With the opt-in the real
hub is reached, and a fetch whose local target is under the developer's real cache base still
refuses: no test writes into the shared base under any setting. Set `JUST_DNA_HUB_GUARD_LOG` to a
file to have every refusal append its test id there, which is how the reaching tests were listed.
Since RM391 the root `conftest.py` fences every client at the transport; this one stays because it
refuses before any socket, with the hub's own remedy in the message, and because its real-base half
holds under the opt-in, where the transport fence steps aside.

**And one opt-in fixture, `no_ambient_caches`, for the test that means "no snapshot" about any lane.**
The PubMind fixture is autouse because *every* lookup test wants it; the general one is not, because
the integration tests (`test_resolver_integration`, the `_needs_snapshot` drafters) deliberately use
whatever the developer's base holds and would turn from *run when present* into *always fail*. So a
test that asserts `no_reference`, `unchecked` or `offline` requests it by name — ten did on
2026-09-04, the day a colleague pulled every publishable snapshot into the configured base and ten
tests that had only ever run against an empty one started reading a real answer where they asserted
an absence. It blanks `CACHE_BASE_VAR` and every lane's `env_var`, walked off `CACHE_LANES` rather
than listed, so a fifteenth lane is covered the day it is declared.
"""

import ast
import functools
import gzip
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import huggingface_hub
import pytest
from just_dna_enricher import civic_draft, clinvar_build, download, locations
from just_dna_enricher.caches import CACHE_LANES
from just_dna_enricher.clingen_allele import ClingenAlleleClient
from just_dna_enricher.mitomap_build import build_snapshot as build_mitomap_snapshot
from just_dna_enricher.mitomap_miss_build import build_miss_snapshot

#: The developer's real cache base, read before any test changes the environment and without exporting
#: the `.env` (`env_value`): the configured base, else the platformdirs default.
_REAL_CACHE_BASE: Path = Path(
    locations.env_value(locations.CACHE_BASE_VAR) or locations.user_cache_dir(appname=locations.APPNAME)
).resolve()
#: Every real directory a provisioner could write into: the base, and each lane's own override where the
#: developer set one outside it.
_REAL_CACHE_ROOTS: tuple[Path, ...] = (_REAL_CACHE_BASE,) + tuple(
    Path(value).resolve() for lane in CACHE_LANES if (value := locations.env_value(lane.env_var))
)
#: The two bodies every `ensure_*` provisions through; `test_the_hub_is_fenced.py` asserts the set.
_PROVISIONERS: tuple[str, ...] = ("_provision_snapshot", "_provision_root_file_snapshot")
_REAL_HF_FILESYSTEM = huggingface_hub.HfFileSystem
_REAL_HF_HUB_DOWNLOAD = huggingface_hub.hf_hub_download


class HubReachedInTests(RuntimeError):
    """A test reached the real HuggingFace hub, or a fetch into the real cache base, without arranging it."""


def _refuse(what: str) -> HubReachedInTests:
    log = os.environ.get("JUST_DNA_HUB_GUARD_LOG")
    test = os.environ.get("PYTEST_CURRENT_TEST", "<unknown test>")
    if log:
        with Path(log).open("a", encoding="utf-8") as fh:
            fh.write(f"{test}\t{what}\n")
    return HubReachedInTests(
        f"{what} from {test}: install a fake hub (monkeypatch huggingface_hub.HfFileSystem), stub the "
        f"lane's `ensure`, or point it at a tmp directory under JUST_DNA_NETWORK_TESTS=1 (RM372)."
    )


def _under_real_base(local: object) -> bool:
    resolved = Path(str(local)).resolve()
    return any(resolved.is_relative_to(root) for root in _REAL_CACHE_ROOTS)


def _network_opted_in() -> bool:
    return os.environ.get("JUST_DNA_NETWORK_TESTS") == "1"


class _FencedHfFileSystem:
    """`HfFileSystem` as the suite sees it: refused offline, and never writing into the real base."""

    def __init__(self, *args, **kwargs) -> None:
        if not _network_opted_in():
            raise _refuse("the real HfFileSystem")
        self._fs = _REAL_HF_FILESYSTEM(*args, **kwargs)

    def get(self, remote_path: str, local_path: str, *args, **kwargs):
        if _under_real_base(local_path):
            raise _refuse(f"a fetch of {remote_path} into the real cache base {_REAL_CACHE_BASE}")
        return self._fs.get(remote_path, local_path, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._fs, name)


def _fenced_hf_hub_download(*args, **kwargs):
    if not _network_opted_in():
        raise _refuse("the real hf_hub_download")
    target = kwargs.get("local_dir") or kwargs.get("cache_dir")
    if target is not None and _under_real_base(target):
        raise _refuse(f"hf_hub_download into the real cache base {_REAL_CACHE_BASE}")
    return _REAL_HF_HUB_DOWNLOAD(*args, **kwargs)


@pytest.fixture
def real_cache_base() -> Path:
    """The developer's real cache base, the one directory no test may fetch into."""
    return _REAL_CACHE_BASE


def _fenced_provisioner(real):
    """`real` (a provisioner taking the cache directory first), refused for a real cache directory.

    At the provisioner, not only at the fetch: `_provision_snapshot` writes its pull record and stages
    the manifest before its first `get`, so a fence at `get` alone would let it rewrite a real record.
    """

    def fenced(cache_dir, *args, **kwargs):
        if _under_real_base(cache_dir):
            raise _refuse(f"a provisioning of the real cache directory {cache_dir}")
        return real(cache_dir, *args, **kwargs)

    return fenced


@pytest.fixture(autouse=True)
def _fenced_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real hub is unreachable unless opted in, and no real cache directory is ever provisioned."""
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _FencedHfFileSystem)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", _fenced_hf_hub_download)
    for name in _PROVISIONERS:
        monkeypatch.setattr(download, name, _fenced_provisioner(getattr(download, name)))


@pytest.fixture
def clingen_registry_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CIViC drafter's default ClinGen client answers 503, so a CAID row is *unchecked* (RM391).

    The CIViC slice's CAID-only rows ask the ClinGen Allele Registry whenever a test passes no
    `registry=`, and most CIViC-draft tests are about the CIViC rows, not the registry. Until RM391 that
    was a live request every run, and the tests passed on whatever came back. The scripted outage is
    the state they had been passing in offline: the real client, its real translation of a failed
    request into `unchecked`, and no egress. A file uses it with `pytestmark`; a test about the registry
    passes its own (`registry=`, `offline=True`), which this does not touch.
    """
    down = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(503)))
    monkeypatch.setattr(
        civic_draft, "ClingenAlleleClient", functools.partial(ClingenAlleleClient, client=down)
    )


#: A CSI escape sequence — what rich emits to colour a span. See `cli_text`.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def _no_ambient_pubmind_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    absent = Path(tmp_path_factory.getbasetemp()) / "no-pubmind-snapshot"
    monkeypatch.setenv(locations.PUBMIND_CACHE_VAR, str(absent))


@pytest.fixture(autouse=True)
def _no_ambient_hf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test sees the developer's `HF_TOKEN`, from the environment or from the repository's `.env`.

    Since RM301 the HuggingFace sites read `env_value("HF_TOKEN")` *before* `get_token()`. The upload
    tests stub `get_token()` as the token's only source, so on a machine whose `.env` holds a real
    publish token that token reached their mocked `HfApi` instead of the stub's, and four tests failed on
    exactly the machine that can publish. Set to empty, never deleted (`@test-no-credential`): an
    exported empty string is present, so the `.env` cannot refill it. A test that wants a token from a
    `.env` runs in a subprocess with the variable stripped, as `test_dotenv_credentials.py` does.
    """
    monkeypatch.setenv("HF_TOKEN", "")


@pytest.fixture
def no_ambient_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Every lane resolves to *nothing*, whatever the developer's `.env` and base hold.

    Set, never deleted (`@test-no-credential`): `load_env` keeps a variable that is present, and a
    deleted one is exactly what lets `.env` refill it. The base is blanked too, because the default
    directory is the other half of the ladder and the half that actually holds a pulled snapshot.
    Returns the directory nothing lives in, for a test that wants to build there afterwards.
    """
    nowhere = tmp_path / "no-ambient-caches"
    monkeypatch.setenv(locations.CACHE_BASE_VAR, str(nowhere))
    for lane in CACHE_LANES:
        monkeypatch.setenv(lane.env_var, str(nowhere))
    return nowhere


# ── the MITOMAP corpus (RM171) ──────────────────────────────────────────────────────────────────
#
# Here rather than in `test_mitomap.py` because two modules read it — the reader/builder tests and the
# derived miss lane's — and pytest test modules are not importable from one another. A corpus copied
# into a second file is a corpus that drifts, which is exactly the failure the miss lane exists to
# report about its own parents.

# ── the fixture ─────────────────────────────────────────────────────────────────────────────────
#
# Row shapes lifted from the real dump, one per case the code has to distinguish. The two variant
# tables carry the same grammar and different fourth columns (`aa` against `rna`), which is why the
# snapshot keeps both rather than folding them.

MMUTATION = [
    # id locus dz allele position refna regna aa cons contr homo hetero status cfrm_date
    "1\tMT-ND1\tLHON\tm.3460G>A\t3460\tG\tA\tA52T\t.\t0\t+\t+\tCfrm [P]\t2010.01.01",
    "2\tMT-ND5\tMELAS\tm.13513G>A\t13513\tG\tA\tD393N\t.\t0\t-\t+\tCfrm [LP]\t\\N",
    "3\tMT-ATP6\tNARP\tm.8993T>G\t8993\tT\tG\tL156R\t.\t0\t+\t+\tCfrm [VUS*]\t\\N",
    "4\tMT-CR\tBD-associated\tm.114C>T\t114\tC\tT\tnoncoding\t.\t.\t+\t-\tReported\t\\N",
    "5\tMT-ATP8/6\tunspecified\tm.8527A>G\t8527\tA\tG\tM1V\t.\t.\tnr\tnr\tReported [VUS]\t\\N",
    "6\tMT-CO1\tdeafness\tm.7402del\t7402\tC\t:\tnoncoding\t.\t.\t-\t+\tReported\t\\N",
    "7\tMT-CYB\tEXIT\tm.15150G>A\t15150\tG\tA\tW135*\t.\t0\t-\t+\tConflicting reports\t\\N",
    "8\tMT-ND2\tLHON modifier\tm.4917A>G\t4917\tA\tG\tN150D\t.\t.\t+\t-\tReported [LB]\t\\N",
]
RTMUTATION = [
    # id locus dz allele position refna regna rna cons contr homo hetero status cfrm_date
    "16\tMT-TL1\tMELAS\tA3243G\t3243\tA\tG\ttRNA Leu\t.\t0\t-\t+\tCfrm [P]\t2020.07.29",
    "17\tMT-TL1\tMELAS\tT3271C\t3271\tT\tC\ttRNA Leu\t.\t0\t-\t+\tCfrm [LP]\t\\N",
    "18\tMT-TF\tclinical lab\tT578C\t578\tT\tC\ttRNA Phe\t91.11%\t0\tnr\t+\tReported [VUS-]\t\\N",
    "19\tMT-RNR1\tdeafness\tA1555G\t1555\tA\tG\t12S rRNA\t.\t0\t+\t+\tUnclear\t\\N",
    "20\tMT-TS1 precursor\thearing loss\tT7511C\t7511\tT\tC\ttRNA Ser\t.\t0\tnr\t+\tReported [B] in hg K,U\t\\N",
    # The one row in the real 1,096 whose allele NAME states a variable number of copies while the
    # allele COLUMNS state one definite pair — the source disagreeing with itself about definiteness.
    # Verbatim, because the point is the shape rather than an invented example.
    "104\tMT-RNR1\tDEAF / AD-associated\tT961delT+ / -C(n)ins\t961\tT\tCC\t12S rRNA\t+\tnd\t+\t+\tReported [LB]\t\\N",
]
MMUTATION_REFERENCE = ["1\t100", "1\t101", "2\t100", "3\t102", "6\t103"]
RTMUTATION_REFERENCE = ["16\t100", "17\t101", "19\t102"]
REFERENCE = [
    # id authors title publication editors volume number pages date city publisher keywords abstract nlmid
    "100\tWallace, D.C.\tMitochondrial DNA mutation\tScience\t.\t242\t4884\t1427-1430\t1988\t.\t.\t.\t.\t3201231",
    "101\tGoto, Y.\tA mutation in tRNA(Leu)\tNature\t.\t348\t6302\t651-653\t1990\t.\t.\t.\t.\t2263545",
    # The one shape the whole-column walk turned up that is not a PMID: an Ovid article id whose
    # first eight characters are digits, which a substring search would happily cite as a paper.
    "102\tSomebody, A.\tAn Ovid-hosted review\tSome Journal\t.\t1\t1\t1-2\t2026\t.\t.\t.\t.\t01930224-202601000-00006",
    # And the other: no `nlmid` at all, 397 of them in the real file.
    "103\tNobody, B.\tAn uncited note\tA Newsletter\t.\t1\t1\t1-2\t1999\t.\t.\t.\t.\t\\N",
]
EDIT_DATE = [
    "45097\tmMut\t2026-08-21",
    "45098\trtMut\t2026-08-19",
    "45091\tref\t2026-08-20",
]

BLOCKS = [
    (
        'COPY mitomap.mmutation (id, locus, dz, allele, "position", refna, regna, aa, cons, contr, '
        "homo, hetero, status, cfrm_date) FROM stdin;",
        MMUTATION,
    ),
    (
        'COPY mitomap.rtmutation (id, locus, dz, allele, "position", refna, regna, rna, cons, contr, '
        "homo, hetero, status, cfrm_date) FROM stdin;",
        RTMUTATION,
    ),
    ("COPY mitomap.mmutation_reference (mmutation_id, reference_id) FROM stdin;", MMUTATION_REFERENCE),
    ("COPY mitomap.rtmutation_reference (rtmutation_id, reference_id) FROM stdin;", RTMUTATION_REFERENCE),
    (
        "COPY mitomap.reference (id, authors, title, publication, editors, volume, number, pages, "
        "date, city, publisher, keywords, abstract, nlmid) FROM stdin;",
        REFERENCE,
    ),
    ("COPY mitomap.edit_date (id, table_name, date) FROM stdin;", EDIT_DATE),
]


def _cli_text(result) -> str:
    """Rendered CLI output flattened to one line, for matching a phrase an operator would grep for.

    **RM233.** Typer renders errors and `--help` through rich, which draws a box at a width
    `CliRunner` pins itself — the environment cannot widen it. A diagnostic longer than the box is
    therefore broken across lines with `│` and padding in the middle of a sentence, so
    `"nothing will fetch it" in result.output` is false for a message that says exactly that. It was
    one of the two failures that made `main` red at `2001215` while every local run was green.

    Colour is handled once, in the root `conftest.py`, by pinning `TERM=dumb`; this is the other half,
    and it cannot live there because no environment variable reaches `CliRunner`'s width. Escapes are
    stripped here too so the helper is correct on its own rather than only in company.

    Use it wherever a test matches **prose**. A test matching a token — a flag name, an exit code, a
    single word — is unaffected by wrapping and does not need it.

    **It reads `stderr` as well, and that is why it takes the result rather than a string.** Typer
    writes a `BadParameter` to stderr, so a helper over `result.output` alone would quietly match
    nothing for exactly the errors worth asserting on.

    It began as `_unwrapped` inside `test_cache_lanes.py`, private, which is the other half of how
    RM233 happened: the second site that needed it could not find it, wrote `in result.output`, and
    was the test that went red. A normalizer with a private name is a normalizer with one caller
    (`@roster-is-as-wide-as-the-tables-it-reads`). Stripping the escapes is new here — the original
    collapsed box drawing and wrapping only, which is why it survived colour and the other did not.
    """
    raw = result.output + (result.stderr if result.stderr_bytes else "")
    plain = _ANSI.sub("", raw)
    # The box characters become spaces rather than vanishing: `│ ends a line │ starts` must not weld
    # two words into one, and every run of whitespace then collapses to a single space.
    for glyph in "│┃╭╮╰╯─━┌┐└┘":
        plain = plain.replace(glyph, " ")
    return " ".join(plain.split())


@dataclass(frozen=True)
class CheckWalk:
    """What a static walk read off `ran(...)`/`skipped(...)` calls: the check names, and the sites it
    could not read. Kept apart so a caller asserting an equality can also refuse a blind spot."""

    #: Every check name passed as a string literal, or as a module-level `NAME = "..."` constant.
    names: frozenset[str]
    #: `file:line` of each call whose first argument the walk could not resolve to a string — a name
    #: built at runtime, an attribute (`record.check`). A walk that skipped them silently would report
    #: an equality over the calls it happened to understand.
    unresolved: tuple[str, ...]


def _checks_written_in(paths) -> CheckWalk:
    """Walk `paths` (files, or packages walked recursively) for the checks their record calls name.

    **RM365: the one walker every file-level check-roster guard calls.** The vocabulary-wide guard in
    `test_verification_record.py` had its own copy, and `DERIVED_PRODUCERS` had none, so its `checks`
    field was asserted only to be vocabulary members and fell three `enrich` checks and one
    `literature` check behind what the passes write. A module-
    level `CHECK = "..."` counts as a literal: a pass naming its check once is better code than one
    repeating the string, and a walk blind to the idiom it should encourage would stop covering it.
    """
    names: set[str] = set()
    unresolved: list[str] = []
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            node.targets[0].id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        # The two constructors under any local name they were imported as (`ran as _ran`), called
        # bare or through a module (`verification.ran(...)`), plus the model built directly with a
        # `check=` — every spelling a record can be made with, so a new one cannot slip past unread.
        constructors = {"ran", "skipped"} | {
            alias.asname
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("verification")
            for alias in node.names
            if alias.name in {"ran", "skipped"} and alias.asname
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if callee in constructors and node.args:
                first = node.args[0]
            elif callee == "VerificationRecord":
                first = next((kw.value for kw in node.keywords if kw.arg == "check"), None)
                if first is None:
                    continue
            else:
                continue
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
            elif isinstance(first, ast.Name) and first.id in constants:
                names.add(constants[first.id])
            else:
                unresolved.append(f"{path.name}:{node.lineno}")
    return CheckWalk(names=frozenset(names), unresolved=tuple(unresolved))


@pytest.fixture
def checks_written_in():
    """`_checks_written_in` as a fixture — the importlib-mode route, as `cli_text` explains."""
    return _checks_written_in


@pytest.fixture
def cli_text():
    """`_cli_text` as a fixture, which is how a conftest helper reaches a test under importlib mode.

    `addopts` carries `--import-mode=importlib`, so `from conftest import …` raises
    `ModuleNotFoundError` — a conftest is loaded as a plugin, not placed on `sys.path`. A fixture is
    the supported route and it keeps the helper's single definition.
    """
    return _cli_text


def write_mitomap_dump(path: Path, blocks=BLOCKS) -> Path:
    """A gzipped `pg_dump` fragment in the shape the real one has, plus a table nothing reads."""
    lines = [
        "--",
        "-- PostgreSQL database dump",
        "--",
        "SET statement_timeout = 0;",
        "",
        "COPY mitomap.code (id, codon, aa) FROM stdin;",
        "1\tTTT\tPhe",
        "\\.",
        "",
    ]
    for header, rows in blocks:
        lines.extend([header, *rows, "\\.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


@dataclass(frozen=True)
class MitomapCorpus:
    """The synthetic dump, and the row lists a test asserts against.

    Handed out as one object rather than as loose module constants, because the two test modules that
    need it are not importable from each other and a corpus copied into a second file is a corpus
    that drifts — which is the failure the miss lane exists to report about its own parents.
    """

    def write(self, path: Path, blocks=None) -> Path:
        return write_mitomap_dump(path, BLOCKS if blocks is None else blocks)

    def without(self, table: str) -> list:
        """The blocks with one table's COPY removed — the dump-is-short-a-table case."""
        return [b for b in BLOCKS if not b[0].startswith(f"COPY mitomap.{table} ")]

    @property
    def mmutation(self) -> list[str]:
        return list(MMUTATION)

    @property
    def references(self) -> list[str]:
        return list(REFERENCE)

    @property
    def mmutation_links(self) -> list[tuple[str, ...]]:
        return [tuple(row.split("\t")) for row in MMUTATION_REFERENCE]


@pytest.fixture
def mitomap_corpus() -> MitomapCorpus:
    return MitomapCorpus()


@pytest.fixture
def mitomap_dump(tmp_path: Path, mitomap_corpus: MitomapCorpus) -> Path:
    """A gzipped MITOMAP `pg_dump` fragment — the parent every MITOMAP test builds from."""
    return mitomap_corpus.write(tmp_path / "mitomap.dump.sql.gz")


# ── the parents the MITOMAP-miss lane joins (RM171) ─────────────────────────────────────────────
#
# A five-record chrMT ClinVar snapshot, cut through `clinvar_build`'s own VCF path rather than
# hand-written as a parquet, so the join runs against the file the real builder produces. The rows are
# chosen against the corpus above to exercise all four buckets and the one trap: 8993 T>C is a
# *different allele at the same position* as MITOMAP's 8993 T>G, so a position-level join would report
# a photocopy where the exact one correctly reports a miss.

CLINVAR_MT_VCF = """##fileformat=VCFv4.1
##fileDate=2026-06-27
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
MT\t3460\t9999\tG\tA\t.\t.\tALLELEID=1;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel;GENEINFO=MT-ND1:4535
MT\t114\t9998\tC\tT\t.\t.\tALLELEID=2;CLNSIG=Benign;CLNREVSTAT=criteria_provided,_single_submitter
MT\t8993\t9997\tT\tC\t.\t.\tALLELEID=3;CLNSIG=Uncertain_significance;CLNREVSTAT=criteria_provided,_single_submitter
MT\t3243\t9996\tA\tG\t.\t.\tALLELEID=4;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
MT\t1555\t9995\tA\tG\t.\t.\tALLELEID=5;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
"""


@pytest.fixture
def clinvar_mt_vcf() -> str:
    """The default chrMT VCF text, so a test can build a *newer* ClinVar out of it.

    A fixture rather than an import: a pytest `conftest` is not an importable module, and a second
    copy of the text in the test that needs to modify it is the drift this file exists to avoid.
    """
    return CLINVAR_MT_VCF


@pytest.fixture
def build_clinvar_mt(tmp_path: Path):
    """A factory: `build_clinvar_mt()` writes `<tmp>/clinvar`, `build_clinvar_mt(other)` rebuilds it.

    A factory rather than a plain fixture because one test needs the *same directory* rebuilt from a
    newer file — which is precisely the case the child's parent pin exists to catch.
    """

    def build(vcf_text: str = CLINVAR_MT_VCF) -> Path:
        vcf = tmp_path / "clinvar.vcf.gz"
        with gzip.open(vcf, "wt", encoding="utf-8") as handle:
            handle.write(vcf_text)
        clinvar_build.build_snapshot(vcf, tmp_path / "clinvar")
        return tmp_path / "clinvar"

    return build


@pytest.fixture
def mitomap_snapshot(tmp_path: Path, mitomap_dump: Path) -> Path:
    """A built MITOMAP snapshot — the first parent."""
    build_mitomap_snapshot(
        mitomap_dump, tmp_path / "mitomap", source_last_modified="Mon, 24 Aug 2026 05:01:10 GMT"
    )
    return tmp_path / "mitomap"


@pytest.fixture
def mitomap_miss_snapshot(tmp_path: Path, mitomap_snapshot: Path, build_clinvar_mt) -> Path:
    """The derived increment, built from both parents through the real join."""
    build_miss_snapshot(mitomap_snapshot, build_clinvar_mt(), tmp_path / "miss")
    return tmp_path / "miss"
