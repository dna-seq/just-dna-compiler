"""No test reaches the real HuggingFace hub unasked, and none writes into the real cache base (RM372).

On 2026-11-04 `test_rebuild_caches_and_prepare_caches_are_the_cli_loops` ran `prepare_caches` on the
real Ensembl lane. The lane had just moved to a new repo, so the developer's recorded cache counted as
another repo's snapshot and was re-pulled: six chromosomes of a cache other sessions were reading
were replaced with another release before the run was stopped. The test needed none of that. It had
always reached the real lane; until the move, the recorded cache was simply left alone.

The fence is one autouse fixture in `conftest.py` (`_fenced_hub`), not a per-test arrangement,
because the defect is a class: any test that reaches a real `ensure_*` or `cache pull` without
arranging its own. These tests show it refusing, and assert that it covers every name the enricher
imports from `huggingface_hub` that can fetch into a local path.
"""

import ast
from pathlib import Path

import huggingface_hub
import just_dna_enricher
import pytest

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent

#: The names the fence replaces: the two that write a remote file into a local path.
_FENCED = frozenset({"HfFileSystem", "hf_hub_download"})
#: The names the enricher imports that fetch nothing into a local path, each with why.
_NOT_A_LOCAL_FETCH = {
    "HfApi": "the publisher's client; its tests stub `_hf_api` and `get_token`, and `HF_TOKEN` is blanked",
    "get_token": "reads a credential; the autouse `_no_ambient_hf_token` blanks the environment's",
    "DEFAULT_IGNORE_PATTERNS": "a constant",
    "CommitOperationAdd": "a commit operation the publisher builds in memory (RM368); it reads and sends "
    "nothing until the stubbed `HfApi` is asked to commit it",
    "CommitOperationDelete": "a deletion the publisher builds in memory (RM386); it removes nothing until "
    "the stubbed `HfApi` is asked to commit it",
    "HfHubHTTPError": "an exception type the publisher catches to tell a moved repo apart (RM386)",
}


def _hub_names() -> set[str]:
    names: set[str] = set()
    for path in _PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("huggingface_hub"):
                names.update(alias.name for alias in node.names)
    return names


def test_every_hub_name_the_enricher_imports_is_fenced_or_says_why_not() -> None:
    assert _hub_names() == _FENCED | set(_NOT_A_LOCAL_FETCH)


def test_the_real_filesystem_refuses_without_the_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "")
    with pytest.raises(RuntimeError, match="the real HfFileSystem"):
        huggingface_hub.HfFileSystem()
    with pytest.raises(RuntimeError, match="the real hf_hub_download"):
        huggingface_hub.hf_hub_download(repo_id="x/y", filename="z", repo_type="dataset")


def test_the_real_base_is_never_a_fetch_target_even_opted_in(
    monkeypatch: pytest.MonkeyPatch, real_cache_base: Path
) -> None:
    """Refused before any request: the target is judged first, so this opens no socket."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "1")
    fs = huggingface_hub.HfFileSystem()
    target = real_cache_base / "ensembl_variations" / "data" / "homo_sapiens-chrMT.parquet"
    with pytest.raises(RuntimeError, match="into the real cache base"):
        fs.get("datasets/just-dna-seq/ensembl_variations_split/data/homo_sapiens-chrMT.parquet", str(target))
    with pytest.raises(RuntimeError, match="into the real cache base"):
        huggingface_hub.hf_hub_download(
            repo_id="x/y", filename="z", repo_type="dataset", local_dir=real_cache_base / "x"
        )


def test_a_test_that_installs_its_own_fake_is_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: sentinel)
    assert huggingface_hub.HfFileSystem() is sentinel


def test_every_provisioning_body_is_fenced() -> None:
    """The fence wraps the provisioners by name, so a third body would slip past it unnamed."""
    import just_dna_enricher.download as dl

    bodies = {name for name in vars(dl) if name.startswith("_provision")}
    assert bodies == {"_provision_snapshot", "_provision_root_file_snapshot"}


def test_a_real_cache_directory_is_never_provisioned(real_cache_base: Path) -> None:
    """Refused before the pull record is written, with or without the network opt-in."""
    import just_dna_enricher.download as dl

    with pytest.raises(RuntimeError, match="provisioning of the real cache directory"):
        dl.ensure_snapshot(real_cache_base / "ensembl_variations")
