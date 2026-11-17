"""`LookupClients` lives in a leaf module, so `enrich.orchestration` can import it at module level (0.9 wave 0).

Importing `lookup` loads `enrich.orchestration` on the way (lookup → pubmind_draft → clinvar_draft →
enrich), so while the bundle was defined in `lookup`, `orchestration` could not name it at the top of
the file without a cycle, and inline imports are banned. RM404 hands the bundle into `enrich()`, so the
bundle moved to `just_dna_enricher.clients`, which imports only the client types it names.

Each probe runs in a fresh interpreter: inside the suite every module is already in `sys.modules`, so
an import-order test there passes whatever the graph is.
"""

import subprocess
import sys

import pytest
from just_dna_enricher import clients, lookup

#: What the leaf must never load. `lookup` and `enrich` are the cycle; a drafter is how `lookup` reaches
#: `enrich`. `drafting` (the drafting scaffold, loaded by the client modules) is not a drafter.
_FORBIDDEN = """
def forbidden(names):
    return sorted(
        n for n in names
        if n == "just_dna_enricher.lookup"
        or n == "just_dna_enricher.enrich"
        or n.startswith("just_dna_enricher.enrich.")
        or n.endswith("_draft")
    )
"""

_LEAF_FIRST = (
    _FORBIDDEN
    + """
import sys
from just_dna_enricher.clients import CLIENT_FIELDS, LookupClients
assert forbidden(sys.modules) == [], forbidden(sys.modules)
import just_dna_enricher.enrich.orchestration
from just_dna_enricher.clients import LookupClients as again
assert again is LookupClients
print("ok", ",".join(CLIENT_FIELDS))
"""
)

_ORCHESTRATION_FIRST = """
import just_dna_enricher.enrich.orchestration
from just_dna_enricher.clients import CLIENT_FIELDS, LookupClients
LookupClients().close()
print("ok", ",".join(CLIENT_FIELDS))
"""


@pytest.mark.parametrize(
    "script", [_LEAF_FIRST, _ORCHESTRATION_FIRST], ids=["leaf_first", "orchestration_first"]
)
def test_the_leaf_imports_alone_and_beside_orchestration(script: str) -> None:
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    head, fields = run.stdout.split()
    assert head == "ok"
    assert tuple(fields.split(",")) == clients.CLIENT_FIELDS


def test_lookup_still_exports_the_same_objects() -> None:
    """Principle 3: `lookup.LookupClients` and `lookup.CLIENT_FIELDS` stay importable, and are the leaf's."""
    assert lookup.LookupClients is clients.LookupClients
    assert lookup.CLIENT_FIELDS is clients.CLIENT_FIELDS
