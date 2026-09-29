"""Reading a credential from `.env` exports nothing into the host's environment (RM301, S124).

Every client used to call `locations.load_env()`, which is `load_dotenv(..., override=False)`: it copies
the *whole* file into `os.environ`. just-module-creator resolves its own settings in layers and reports
which layer each value came from, and after constructing one of our clients every value in its `.env`
read as an exported shell variable. `env_value` reads the one key with the same precedence (an exported
variable wins, an exported empty string stays empty) and writes nothing.

RM100's guarantee still holds and is asserted beside it: the credential reaches the client from a
`.env` alone, whatever the call order.

**The probes run in a subprocess.** The point is what a constructor leaves behind in `os.environ`, and
an in-process test inherits whatever the developer has exported and whatever an earlier test loaded.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import just_dna_enricher
import pytest
from just_dna_enricher import net
from just_dna_enricher.locations import env_value, missing_credential_reason

_FILE = {
    "NCBI_API_KEY": "ncbi-from-dotenv",
    "JUST_DNA_CONTACT_EMAIL": "curator@dotenv.invalid",
    "PHARMVAR_API_KEY": "pharmvar-from-dotenv",
    "JUST_DNA_HTTP_RETRY_ATTEMPTS": "7",
    "A_HOST_SETTING_THE_ENRICHER_NEVER_READS": "host-owned",
}

_PROBE = """
import json, os
from just_dna_enricher.eutils import EutilsSettings
from just_dna_enricher.literature import CrossrefClient, PmcIdConverterClient
from just_dna_enricher.pharmvar import PharmVarClient
from just_dna_enricher.net import retry_attempts

eutils = EutilsSettings()
crossref = CrossrefClient()
converter = PmcIdConverterClient()
pharmvar = PharmVarClient()
print(json.dumps({
    "ncbi": eutils.api_key,
    "eutils_email": eutils.email,
    "crossref_email": crossref.contact_email,
    "converter_email": converter.contact_email,
    "pharmvar": pharmvar.configured,
    "attempts": retry_attempts(3),
    "exported": sorted(k for k in %r if k in os.environ),
}))
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A working directory whose `.env` is the only place any of these variables exists."""
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text("".join(f"{k}={v}\n" for k, v in _FILE.items()), encoding="utf-8")
    return work


def _probe(cwd: Path, **exported: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _FILE}
    env.update(exported)
    done = subprocess.run(
        [sys.executable, "-c", _PROBE % (sorted(_FILE),)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_clients_read_their_credentials_from_the_dotenv_and_export_none_of_it(workspace: Path) -> None:
    seen = _probe(workspace)
    assert seen["ncbi"] == _FILE["NCBI_API_KEY"]
    email = _FILE["JUST_DNA_CONTACT_EMAIL"]
    assert (seen["eutils_email"], seen["crossref_email"], seen["converter_email"]) == (email, email, email)
    assert seen["pharmvar"] is True
    assert seen["attempts"] == int(_FILE["JUST_DNA_HTTP_RETRY_ATTEMPTS"])
    assert seen["exported"] == [], "a client exported the .env into the host's environment"


def test_an_exported_variable_still_wins_over_the_file(workspace: Path) -> None:
    seen = _probe(workspace, NCBI_API_KEY="ncbi-exported")
    assert seen["ncbi"] == "ncbi-exported"
    assert seen["exported"] == ["NCBI_API_KEY"]


def test_an_exported_empty_value_stays_empty_and_the_two_empties_are_told_apart(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("PHARMVAR_API_KEY", "")
    assert env_value("PHARMVAR_API_KEY") == ""
    assert "unset PHARMVAR_API_KEY" in missing_credential_reason("PHARMVAR_API_KEY")

    (workspace / ".env").write_text("PHARMVAR_API_KEY=\n", encoding="utf-8")
    monkeypatch.delenv("PHARMVAR_API_KEY")
    assert env_value("PHARMVAR_API_KEY") == ""
    assert "set EMPTY in the `.env`" in missing_credential_reason("PHARMVAR_API_KEY")
    assert "PHARMVAR_API_KEY" not in os.environ


def test_the_retry_floor_rereads_an_exported_value_after_memoizing_the_file(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(workspace)
    # Both memo cells are restored afterwards: leaving `_file_attempts` at this `.env`'s value raised
    # the retry floor for every later test in the process.
    monkeypatch.setattr(net, "_env_loaded", False)
    monkeypatch.setattr(net, "_file_attempts", None)
    monkeypatch.delenv(net.RETRY_ATTEMPTS_ENV, raising=False)
    assert net.retry_attempts(3) == int(_FILE["JUST_DNA_HTTP_RETRY_ATTEMPTS"])
    monkeypatch.setenv(net.RETRY_ATTEMPTS_ENV, "9")
    assert net.retry_attempts(3) == 9
    assert net.RETRY_ATTEMPTS_ENV in os.environ and os.environ[net.RETRY_ATTEMPTS_ENV] == "9"


def test_only_the_cache_resolvers_export_the_dotenv() -> None:
    """An AST walk: `load_env()` is called in `locations` and nowhere else in the tier.

    `load_env` exports the whole file, and a cache resolver is the one caller documented to do that
    (with `load_dotenv_file=False` to decline). A credential reader that calls it again is S124 back.
    """
    package = Path(just_dna_enricher.__file__).parent
    callers = set()
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name == "load_env":
                    callers.add(path.relative_to(package).as_posix())
    assert callers == {"locations.py"}
