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
"""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_ambient_pubmind_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    absent = Path(tmp_path_factory.getbasetemp()) / "no-pubmind-snapshot"
    monkeypatch.setenv("JUST_DNA_PUBMIND_CACHE", str(absent))
