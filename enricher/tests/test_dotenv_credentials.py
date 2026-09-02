"""Credentials that live only in a `.env` — the two paths that were not reading it.

CLAUDE.md's rule is `@credential-where-read`: load the file at the point the credential is read,
never as a side effect of some other call. Four paths in this tier already did (`net`, `eutils`,
`literature`, `pharmvar`). Two did not, and both were found by an operator asking whether the new
`cache rebuild` endpoint handles a `.env` — it did not, and the failure was silent in the worst
possible direction for one of them.

* **`caches._rebuild_pharmvar` read `os.environ` directly** to decide whether a key is configured at
  all — the split between *not run* (no key, by design) and *failed* (a key that broke). But
  `PharmVarClient.__init__` calls `load_env()` **before** reading the same variable, so a key living
  only in a `.env` was visible to the builder and invisible to the guard standing in front of it. The
  lane reported "no `$PHARMVAR_API_KEY` is set" and never built, on exactly the machine most likely
  to have one. A pre-check that answers differently from the code it guards is worse than no
  pre-check.
* **`upload._hf_api` called `get_token()`**, which reads the real environment and
  `~/.cache/huggingface/token` and neither is a `.env` — so a publish from a workspace that keeps
  `HF_TOKEN` there raised *"No HuggingFace token found"*.

**Every probe runs in a subprocess.** `load_env` mutates `os.environ` for the rest of the process, so
an in-process test would leak the repository's own `.env` into whatever ran next — and, worse, would
pass for the wrong reason on a developer machine that has the variables exported. The environment
handed to each child has them stripped, so the `.env` written by the test is the only possible source.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_STRIPPED = ("PHARMVAR_API_KEY", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_HOME")


def _run(script: str, cwd: Path) -> str:
    """Run a probe with every real credential stripped, so only the `.env` beside `cwd` can supply one.

    `HF_HOME` goes too, and is redirected at an empty directory: `get_token()` falls back to
    `~/.cache/huggingface/token`, so without this the HuggingFace probes pass on any machine where a
    developer has ever run `hf auth login` — green on the laptop, and silent about the defect.
    """
    env = {k: v for k, v in os.environ.items() if k not in _STRIPPED}
    env["HF_HOME"] = str(cwd / "empty-hf-home")
    done = subprocess.run(
        [sys.executable, "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A working directory whose `.env` is the only place either credential exists."""
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text(
        "PHARMVAR_API_KEY=a-key-from-the-dotenv\nHF_TOKEN=hf_a_token_from_the_dotenv\n",
        encoding="utf-8",
    )
    return work


_PHARMVAR_GUARD = """
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest
import just_dna_enricher.caches as caches
import just_dna_enricher.pharmvar_build as pb
from just_dna_enricher.pharmvar import PharmVarError

# Stop at the guard: the point under test is which branch it takes, not whether PharmVar answers.
# The stub raises the type the adapter catches, so reaching it produces an OUTCOME rather than a
# traceback — a bare RuntimeError escapes the adapter and the child exits non-zero for a second
# reason, which would make this test pass or fail for reasons unrelated to the credential.
pb.build_snapshot = lambda *a, **k: (_ for _ in ()).throw(PharmVarError("reached the builder"))
outcome = caches.rebuild_lane(
    LANES_BY_NAME["pharmvar"],
    RebuildRequest(out_dir=__import__("pathlib").Path("out"), declared_use="non_commercial"),
)
print(outcome.built, outcome.detail[:40])
"""


def test_a_pharmvar_key_that_lives_only_in_a_dotenv_reaches_the_guard(workspace: Path) -> None:
    """The lane must get past *no key configured* and on to the builder.

    `built is False` here is the **success** condition: the stub raises, so reaching it at all proves
    the guard read the key. The failure this pins returns `None` — the designed third state, claimed
    wrongly — which would leave the lane permanently unbuilt with a message saying to set a variable
    that is already set.
    """
    built, detail = _run(_PHARMVAR_GUARD, workspace).split(" ", 1)
    assert built == "False", f"the guard claimed no key was configured: {detail}"
    assert "reached the builder" in detail


_PHARMVAR_WITHOUT_THE_FIX = """
import os, pathlib
import just_dna_enricher.caches as caches
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest
import just_dna_enricher.pharmvar_build as pb
from just_dna_enricher.pharmvar import PharmVarError

caches.load_env = lambda override=False: None      # the arrangement before the repair
pb.build_snapshot = lambda *a, **k: (_ for _ in ()).throw(PharmVarError("reached the builder"))
outcome = caches.rebuild_lane(
    LANES_BY_NAME["pharmvar"],
    RebuildRequest(out_dir=pathlib.Path("out"), declared_use="non_commercial"),
)
print(outcome.built, outcome.detail[:40])
"""


def test_without_the_load_the_guard_really_did_claim_there_was_no_key(workspace: Path) -> None:
    """The old behaviour demonstrated on the old arrangement, not asserted about the new one."""
    built, detail = _run(_PHARMVAR_WITHOUT_THE_FIX, workspace).split(" ", 1)
    assert built == "None"
    assert "PHARMVAR_API_KEY" in detail


_HF_TOKEN = """
from just_dna_enricher.upload import _hf_api
api = _hf_api("just-dna-seq/strchive")
print("resolved" if api is not None else "none")
"""


def test_an_hf_token_that_lives_only_in_a_dotenv_authenticates_a_publish(workspace: Path) -> None:
    """`get_token()` reads the real environment and the hub's own token file — a `.env` is neither."""
    assert _run(_HF_TOKEN, workspace) == "resolved"


_HF_WITHOUT_THE_FIX = """
import just_dna_enricher.upload as upload
upload.load_env = lambda override=False: None      # the arrangement before the repair
try:
    upload._hf_api("just-dna-seq/strchive")
    print("resolved")
except PermissionError as exc:
    print("refused")
"""


def test_without_the_load_a_publish_really_did_refuse(workspace: Path) -> None:
    assert _run(_HF_WITHOUT_THE_FIX, workspace) == "refused"


def test_an_exported_variable_still_outranks_the_dotenv(workspace: Path) -> None:
    """`load_env` uses `override=False`, so loading the file never silently replaces a real one.

    Worth pinning at each new call site rather than trusting the loader: an operator who exports a
    token for one run expects that run to use it, and this is the property that makes adding a load
    to a credential path safe rather than a behaviour change.
    """
    env = {k: v for k, v in os.environ.items() if k not in _STRIPPED}
    env["HF_HOME"] = str(workspace / "empty-hf-home")
    env["HF_TOKEN"] = "hf_exported_wins"
    done = subprocess.run(
        [sys.executable, "-c",
         "from just_dna_enricher.locations import load_env\n"
         "load_env()\n"
         "import os; print(os.environ['HF_TOKEN'])"],
        cwd=workspace, env=env, capture_output=True, text=True, check=True,
    )
    assert done.stdout.strip() == "hf_exported_wins"
