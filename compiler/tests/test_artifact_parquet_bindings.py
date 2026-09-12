"""Every parquet the artifact carries is bound to the CSV it comes from, by a walked registry.

**Why this exists.** `ARTIFACT_PARQUETS` is the list of what a compile writes, and until
`SNP_CORE_PARQUETS` was extracted it was the only place three of those names appeared as anything but
a literal inside `_write_*`. So *"which parquet does `variants.csv` become"* had no answer a program
could give — and it has two callers that need one: `ARTIFACT_PARQUETS` itself, and the docs site's
generated per-table reference, which must derive the row rather than hand-keep a fourth copy
(`@fieldnames-from-model`).

`compiler.table_bindings()` is the assembler, public so the generator and this test read one
copy rather than two. The assertion is the **equality**, not the count (`@registry-completeness`): the union of every
registry's parquets is exactly `ARTIFACT_PARQUETS`, so a new table kind whose binding is spelled at its
write site instead of in a registry fails here rather than silently missing a reference page. A count
would hold while the sets disagreed by one in each direction.
"""

import just_dna_compiler.compiler as C
from just_dna_compiler.draft import DRAFTABLE
from just_dna_compiler.hints import DERIVED_TABLE_MODELS


def test_every_artifact_parquet_is_bound_to_the_csv_it_comes_from() -> None:
    produced = {parquet for parquets in C.table_bindings().values() for parquet in parquets}
    assert produced == set(C.ARTIFACT_PARQUETS), (
        "the csv→parquet registries and ARTIFACT_PARQUETS disagree. Missing a binding means a parquet "
        "is written by a literal at its own write site, which no reference page can find; the other "
        "direction means a registry names a parquet the compile never produces. Only in the "
        f"registries: {sorted(produced - set(C.ARTIFACT_PARQUETS))}; only in ARTIFACT_PARQUETS: "
        f"{sorted(set(C.ARTIFACT_PARQUETS) - produced)}"
    )


def test_variants_csv_becomes_two_parquets_and_that_is_load_bearing() -> None:
    """The asymmetry the binding is a tuple-per-csv for.

    `weights` carries the authored surface *minus* `gene`/`phenotype`/`category`; `annotations` carries
    nine columns *including* those three. A single-parquet spelling would have to pick one and be wrong
    about the other, and a consumer reading `weights.parquet` alone genuinely cannot see a gene symbol.
    """
    assert C.SNP_CORE_PARQUETS["variants.csv"] == ("weights.parquet", "annotations.parquet")
    assert len(C.SNP_CORE_PARQUETS["variants.csv"]) == 2


def test_every_bound_csv_has_a_model_in_one_of_the_authored_or_derived_registries() -> None:
    """A table that produces a parquet is describable — which is what the reference pages need.

    Asymmetric on purpose: `overrides.csv` is authored and in `DRAFTABLE`, the fact tables are in
    `DERIVED_TABLE_MODELS`, and `variants.csv`/`studies.csv` are in `DRAFTABLE`. Any csv that produces a
    parquet and appears in neither registry is a page the generator cannot write.
    """
    described = set(DRAFTABLE) | set(DERIVED_TABLE_MODELS)
    undescribable = sorted(set(C.table_bindings()) - described)
    assert not undescribable, (
        "these CSVs produce a parquet but no registry binds them to a model, so nothing can describe "
        f"their columns: {undescribable}"
    )
