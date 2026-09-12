"""One reference page per table kind, generated from the models at docs-build time.

**Why generated and not written.** `just-module-creator` keeps 27 hand-written per-table dossiers, and
on 2026-09-12 they were audited against format/compiler 0.6.1 while the tree was at 0.7.0: two table
kinds added in 0.7 (`clin_sig_authority_calls.csv`, `expression_effects.csv`) had no dossier at all, and
their own banner says the `file:line` citations have drifted. That is not carelessness, it is what
`CLAUDE.md` means by *a command-surface table rots silently* — nothing reads it, so nothing reports the
gap. Everything on these pages is instead derived from a walked registry or from
`reference.authoring_reference()`, which exists precisely as "the drift-proof description consumers
render **instead of** a hand-kept spec dump". A new table kind gets a page by construction.

**The boundary this does not cross.** These pages are a *schema reference*: what the columns are, who
may write them, what the table becomes. They carry **no procedure** — no "run this, then that". The
authoring workflow lives in `just-module-creator` and this repository deliberately carries no authoring
document (`CLAUDE.md`, and its dogfooding predecessor was deleted on 2026-09-03). The dossiers keep what
a model cannot state — an author's framing, the symptom when a table goes wrong — and can cite these
pages instead of restating their columns.

Hand-written prose lives in `docs/TABLES.md`, one `## <csv name>` section per table, spliced in above the
generated facts. That file is an **input** to the build rather than a page of its own: `mkdocs.yml`'s
`exclude_docs` keeps it from publishing twice, and `schema/tests/test_docs_site_nav.py` treats build
inputs as the third half of the partition over `docs/`.
"""

import re
from pathlib import Path

import just_dna_compiler.compiler as compiler
import mkdocs_gen_files
from just_dna_compiler.draft import DRAFTABLE
from just_dna_compiler.hints import DERIVED_TABLE_MODELS
from just_dna_format.base import field_category
from just_dna_format.layout import DEPRECATED_SPELLINGS, sidecar_key, sidecar_spellings
from just_dna_format.reference import authoring_reference

_ROOT = Path(__file__).resolve().parents[1]
_PROSE = _ROOT / "docs" / "TABLES.md"
_LINK = re.compile(r"(\[[^\]]*\]\(\s*)([^)\s]+)(\s*\))")


def _models_by_csv() -> dict[str, type]:
    """`csv -> row model`, authored and derived together, with the deprecated spelling dropped.

    `DRAFTABLE` covers the authored surface (including `variants.csv` and `studies.csv`, which no
    table-kind registry carries) and `DERIVED_TABLE_MODELS` the derived facts. `sources.csv` is in
    `DEPRECATED_SPELLINGS` and shares `SourceRow` with `licensing.csv`, so it gets no page of its own —
    the current name's page names it instead. Counting both would make any roster assertion wrong by one
    by construction.
    """
    bound: dict[str, type] = {**DERIVED_TABLE_MODELS, **DRAFTABLE}
    return {csv: model for csv, model in bound.items() if csv not in DEPRECATED_SPELLINGS}


def _api_path(model: type) -> str:
    """The generated API page for a model, so the two halves of the site join up."""
    return "../api/" + model.__module__.replace(".", "/") + f"/#{model.__module__}.{model.__qualname__}"


def _identity_rows(csv_name: str, model: type) -> list[tuple[str, str]]:
    """The identity card — every row derived from a registry, and a row with no registry is omitted.

    **Every registry lookup goes through `layout.sidecar_key` and this is not defensive.** The licence
    table has two legal spellings and the registries are keyed on the deprecated one (`sources.csv`)
    while the page is written under the current one (`licensing.csv`), so the first version of this
    function reported `licensing.csv` as having no parquet and no fact signature — both false, both
    silently, on a page that rendered perfectly and passed `--strict`. That is `@sidecar-name-and-place`
    verbatim: *a map keyed on one spelling answers the other as a table it never heard of*. Found by
    reading the built page, which is the only thing that catches it.

    **Then the repair introduced a second silent wrong answer, which is the more useful lesson.** The
    natural-key row rebound `key` to a tuple of column names, shadowing the spelling key, so every
    table's fact-signature and attestation rows read "no" — the nine that carry a fact signature
    included. Both defects rendered a perfect page, passed `--strict`, resolved every link and
    partitioned the nav; neither was findable except by reading a page against the registries. That is
    why `_check` runs at build time: a generated page needs an assertion, not a green build.
    """
    ref = authoring_reference()
    bindings = compiler.table_bindings()
    key = sidecar_key(csv_name)
    rows: list[tuple[str, str]] = [
        ("Row model", f"[`{model.__qualname__}`]({_api_path(model)}) (`{model.__module__}`)"),
    ]

    parquets = bindings.get(key, ())
    if parquets:
        lead = [p for p in parquets if p in compiler.LEAD_PARQUETS]
        becomes = ", ".join(f"`{p}`" for p in parquets)
        rows.append(
            (
                "Becomes",
                becomes + (f" — **lead parquet**: {', '.join(f'`{p}`' for p in lead)}" if lead else ""),
            )
        )
    else:
        rows.append(("Becomes", "no parquet — see the prose above for where its content goes"))

    authored = any(sp in DRAFTABLE for sp in sidecar_spellings(csv_name))
    derived = any(sp in DERIVED_TABLE_MODELS for sp in sidecar_spellings(csv_name))
    if authored and derived:
        kind = "**both** — authored, and also written by an enricher pass"
    elif authored:
        kind = "**authored** — a person writes it (a drafter may append rows)"
    else:
        kind = "**derived** — an enricher pass writes it; an author corrects it via `overrides.csv`"
    rows.append(("Authored or derived", kind))
    rows.append(("Draftable", "yes — `draft` can append rows" if authored else "no"))

    natural_key = getattr(model, "_KEY_FIELDS", None)
    if natural_key:
        rows.append(("Natural key", ", ".join(f"`{k}`" for k in natural_key)))

    fact = {csv for csv, _, _ in compiler._FACT_TABLES}
    rows.append(("Fact signature", "yes — its sidecar carries one" if key in fact else "no"))
    rows.append(
        (
            "In the attestation binding",
            "yes — `manifest.inputs[]`" if key in compiler._INPUT_FILES else "no",
        )
    )

    # Asked of `layout`, which owns the spellings, rather than of a set membership that happened to
    # produce the right answer for the one table that has two names.
    deprecated = [sp for sp in sidecar_spellings(csv_name) if sp in DEPRECATED_SPELLINGS]
    if deprecated:
        rows.append(
            ("Also accepted as", ", ".join(f"`{sp}`" for sp in deprecated) + " — deprecated, removed at 1.0")
        )

    any_of = ref["required_any_of"].get(model.__qualname__)
    if any_of:
        groups = " **or** ".join("+".join(f"`{c}`" for c in group) for group in any_of)
        rows.append(("Requires at least one of", groups))
    return rows


def _field_table(model: type) -> list[str]:
    """The column table, from `authoring_reference()` — the surface it exists to keep drift-free."""
    fields = authoring_reference()["models"].get(model.__qualname__)
    if not fields:
        return ["*No field description is published for this model.*\n\n"]
    lines = ["| Column | Type | Required | Values | Meaning |\n", "|---|---|---|---|---|\n"]
    for f in fields:
        category = {"required": "**required**", "defaulted": "defaulted", "optional": "optional"}[
            f.get("category", field_category(model, f["name"]))
        ]
        options = f.get("options")
        if options:
            closed = "one of" if f.get("closed") else "suggested"
            values = f"{closed}: " + ", ".join(f"`{o}`" for o in options)
        else:
            values = ""
        meaning = (f.get("description") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{f['name']}` | `{f['type']}` | {category} | {values} | {meaning} |\n")
    lines.append("\n")
    return lines


def _prose_sections() -> dict[str, str]:
    """`csv name -> the hand-written body` from `docs/TABLES.md`, keyed on its `## <csv>` headings."""
    if not _PROSE.exists():
        return {}
    text = _PROSE.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    parts = re.split(r"^## +(\S+\.csv)\s*$", text, flags=re.MULTILINE)
    for name, body in zip(parts[1::2], parts[2::2], strict=True):
        out[name] = body.strip()
    return out


def _rewrite(body: str) -> str:
    """Links in a spliced section climb one level: `TABLES.md` is at `docs/`, its page at `tables/`.

    Missed once already in this session on a file moved into `docs/history/`, and it fails silently —
    `test_doc_links.py` checks `TABLES.md` where it actually lives, so the spliced copies would 404 while
    the suite stayed green.
    """

    def fix(m: re.Match[str]) -> str:
        target = m[2]
        if target.startswith(("http://", "https://", "#", "mailto:", "../")):
            return m[0]
        return m[1] + "../" + target + m[3]

    return _LINK.sub(fix, body)


def _check(cards: dict[str, list[tuple[str, str]]]) -> None:
    """Assert the identity cards against the registries, at build time, page by page.

    Both defects `_identity_rows` documents were invisible to `--strict`, because a wrong answer is still
    valid HTML. So the two properties are asserted instead of eyeballed, and a failure fails the build.

    The fact-signature side is compared as a **set of spelling keys**, never as a count, for the reason
    the original answer was wrong: `sources.csv` and `licensing.csv` are one table with two names, so
    `len(_FACT_TABLES)` and the number of pages saying "yes" legitimately differ by one. A count
    assertion would have to encode that off-by-one; a set dissolves it.
    """
    bound = compiler.table_bindings()
    for csv_name, card in cards.items():
        if sidecar_key(csv_name) in bound:
            becomes = dict(card)["Becomes"]
            assert "no parquet" not in becomes, (
                f"{csv_name} is bound to {bound[sidecar_key(csv_name)]} but its page says it becomes no "
                "parquet — a registry lookup missed the spelling key"
            )
    # **Compared as models rather than as names, and the honest reason is narrower than the one first
    # written here.** The rule is a peer session's, reached from its own generator the same day: compute
    # the ground truth by a path that does not repeat the step under suspicion, or the assertion restates
    # the bug. The suspect step here is normalising a CSV name through `sidecar_key`, so comparing row
    # models — identity-comparable, carrying no spelling at all — is the independent path.
    #
    # **But the blind spot that justified the change turned out not to exist, measured rather than
    # assumed.** Stubbing `sidecar_key` to the identity function fails the *name*-based comparison too,
    # because the page side of it is keyed on pages that already exclude `DEPRECATED_SPELLINGS` while the
    # registry side does not — so the two disagree on `sources.csv` whatever the normaliser does. What the
    # model comparison actually buys is a failure message that names a model instead of a spelling, and
    # independence as a property rather than as a repair. Kept for that, and the reasoning corrected here
    # rather than left standing as a fix for a defect this file never had.
    models = _models_by_csv()
    fact_models = {model for _, _, model in compiler._FACT_TABLES}
    claimed_models = {
        models[csv] for csv, card in cards.items() if dict(card)["Fact signature"].startswith("yes")
    }
    assert claimed_models == fact_models, (
        "the pages claiming a fact signature disagree with `_FACT_TABLES`. Only on a page: "
        f"{sorted(m.__qualname__ for m in claimed_models - fact_models)}; only in the registry: "
        f"{sorted(m.__qualname__ for m in fact_models - claimed_models)}"
    )


def _write_pages() -> None:
    models = _models_by_csv()
    prose = _prose_sections()
    summary: list[str] = []
    cards: dict[str, list[tuple[str, str]]] = {}
    for csv_name, model in sorted(models.items()):
        slug = csv_name.removesuffix(".csv")
        doc = Path("tables", slug).with_suffix(".md")
        cards[csv_name] = _identity_rows(csv_name, model)
        with mkdocs_gen_files.open(doc, "w") as fh:
            fh.write(f"# `{csv_name}`\n\n")
            if csv_name in prose:
                fh.write(_rewrite(prose[csv_name]) + "\n\n")
            fh.write("## Identity\n\n")
            for label, value in cards[csv_name]:
                fh.write(
                    f"| {label} | {value} |\n"
                    if label != "Row model"
                    else f"| | |\n|---|---|\n| {label} | {value} |\n"
                )
            fh.write("\n## Columns\n\n")
            fh.writelines(_field_table(model))
            fh.write(
                "*Generated from the row model at build time — `reference.authoring_reference()`, the same "
                "answer `describe_table` gives an authoring tool. Nothing on this page is hand-kept.*\n"
            )
        mkdocs_gen_files.set_edit_path(
            doc, "../docs/TABLES.md" if csv_name in prose else "../scripts/gen_table_pages.py"
        )
        summary.append(f"- [{csv_name}]({slug}.md)\n")
    with mkdocs_gen_files.open("tables/SUMMARY.md", "w") as fh:
        fh.writelines(summary)
    _check(cards)


_write_pages()
