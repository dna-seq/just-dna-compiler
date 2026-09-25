"""Cross-table and per-kind checks: haplotype definitions, phase ambiguity, studies, per-kind dedup
keys, and misspelled table names.
"""

import difflib
from collections import defaultdict
from pathlib import Path
from typing import Any

from just_dna_format.base import derive_variant_key
from just_dna_format.binning import MeasureBinRow, format_group_key, validate_bins
from just_dna_format.findings import CodedWarning, restate
from just_dna_format.layout import DERIVED_SUBDIR, VERIFICATION_JSON, sidecar_spellings
from just_dna_format.spec import StudyRow, VariantRow
from pydantic import BaseModel

from just_dna_compiler.compiler.tables import (
    _DERIVED_FILES,
    _FACT_TABLES,
    _PROVENANCE_FILE,
    _TABLE_DUPE_KEYS,
    _TABLE_KIND_CSVS,
    OVERRIDES_CSV,
)

#: The reference star allele. Defined by carrying **none** of a gene's variants, so it can never
#: appear in `haplotypes.csv` and must never be reported as undefined.
_REFERENCE_HAPLOTYPE = "*1"


def _cross_validate_haplotype_definitions(
    haplotypes: list[Any], allele_functions: list[Any], diplotypes: list[Any]
) -> list[str]:
    """Warn when a star allele is *used* but never *defined*. Returns warnings.

    Validate-by-redundancy across the PGx tables: `allele_function.csv` says what an allele does and
    `diplotypes.csv` pairs it, while `haplotypes.csv` says which variants make it. An allele named by
    the first two and absent from the third cannot be called from a VCF at all, so every row about it
    is dead weight — a consumer's star-allele caller will never emit it.

    Only checked when `haplotypes.csv` is **present**: a module may legitimately carry a diplotype
    table alone and lean on the caller's own definitions, and punishing that would be the
    orphan-sidecar mistake (don't fault an author for a file they deliberately did not write).

    Found by drafting CYP2C19 from CPIC: `*36`, `*37` and `*42` were used across 666 diplotype rows,
    two of them declared `no_function`, and nothing defined any of them.
    """
    if not haplotypes:
        return []
    defined = {row.haplotype_name for row in haplotypes}
    used: dict[str, set[str]] = {}
    for row in allele_functions:
        used.setdefault(row.allele, set()).add("allele_function.csv")
    for row in diplotypes:
        for allele in (row.haplotype_a, row.haplotype_b):
            used.setdefault(allele, set()).add("diplotypes.csv")
    undefined = sorted(allele for allele in used if allele not in defined and allele != _REFERENCE_HAPLOTYPE)
    if not undefined:
        return []
    return [
        CodedWarning(
            "star_allele_undefined",
            f"Star allele(s) used but not defined in haplotypes.csv: {undefined}. A consumer's caller "
            f"cannot emit an allele nothing defines, so rows about it can never match.",
        )
    ]


#: An allele a haplotype does not mention — or mentions as its own reference base. The letter never
#: has to be known: "unmentioned" means the same thing for every haplotype at a given variant, so two
#: haplotype sets can be compared without a reference sequence anywhere in the compiler (P2).
_IMPLIED_REFERENCE = "\0ref"


def _unphased_signature(
    pair: tuple[str, str], definitions: dict[str, dict[tuple, str]], variants: list[tuple]
) -> tuple:
    """The genotype a consumer *observes* for a diplotype, with phase discarded.

    Per variant, the **sorted pair** of alleles the two haplotypes contribute — sorted because that
    is precisely what losing phase does: it tells you which two alleles are present and not which
    chromosome each sits on.
    """
    return tuple(
        tuple(
            sorted(
                (
                    definitions.get(pair[0], {}).get(variant, _IMPLIED_REFERENCE),
                    definitions.get(pair[1], {}).get(variant, _IMPLIED_REFERENCE),
                )
            )
        )
        for variant in variants
    )


def _cross_validate_phase_ambiguity(haplotypes: list[Any], diplotypes: list[Any]) -> list[str]:
    """Warn when two diplotype rows are indistinguishable without phase and disagree. Warnings only.

    **The narrow, real residue of RM28's cis/trans motivation.** Compound heterozygosity is the case
    that most justified a predicate language, and it turns out to need none: `haplotypes.csv` is a
    junction table so a haplotype is same-strand conjunction, and a *diplotype* is a statement about
    two homologs — so cis and trans are already two rows. `reference_examples/hfe_compound_het/`
    writes exactly that, with the bricks that shipped in 0.4.

    What no table can say is that the two rows **cannot be told apart from unphased data**. HFE
    `C282Y/H63D` (in trans, no wild-type protein on either chromosome, an at-risk genotype) and
    `C282Y-H63D` + `wt` (both variants on one chromosome, one intact copy, a carrier) present the
    identical unphased genotype — rs1800562 G/A and rs1799945 C/G — and carry opposite conclusions.
    A consumer with unphased calls that silently picks the first would manufacture a finding; picking
    the second would suppress one.

    It is a **check** rather than a column because it is derivable: the compiler already holds both
    tables and the computation is pure and offline, which is the validate-by-redundancy class this
    tier exists for. Adding a `requires_phase` column instead would make an author restate something
    the data already determines, and it would go stale the moment a haplotype is edited.

    **Closed-world, and deliberately so.** It compares the rows a module states, never the rows it
    omits. APOE is the standing illustration: ε2/ε4 and ε1/ε3 are the textbook unphased collision, and
    `reference_examples/apoe_epsilon/` carries no ε1, so nothing here fires. That is correct — the
    module makes no claim about ε1 — and the neighbouring "used but not defined" check is what covers
    an allele a caller might emit that the module never describes.

    A haplotype that does not mention a variant is treated as carrying the reference there, and an
    allele explicitly equal to the row's own `ref` normalizes to the same sentinel. Neither needs the
    reference *sequence*: only that "unmentioned" means one thing. That is what lets this run on a
    CPIC-drafted table, where haplotypes are sparse and `ref` is absent entirely — and on such a table
    it correctly finds nothing, because sparse definitions genuinely do not collide.
    """
    if not haplotypes or not diplotypes:
        return []

    definitions: dict[str, dict[tuple, str]] = {}
    variants: list[tuple] = []
    for row in haplotypes:
        # Position-level, and *without* `alts`: a haplotype names one allele at a locus, so the key
        # must be the place. Passing `alts` would mint a per-allele VRS id and put each haplotype's
        # own allele in a different bucket, which is the mixing-up `derive_variant_key` warns about.
        variant = derive_variant_key(row.rsid, row.chrom, row.start, row.ref)
        if variant is None:
            continue
        if variant not in definitions.get(row.haplotype_name, {}) and variant not in variants:
            variants.append(variant)
        allele = _IMPLIED_REFERENCE if row.ref is not None and row.allele == row.ref else row.allele
        definitions.setdefault(row.haplotype_name, {})[variant] = allele

    # A diplotype naming a haplotype `haplotypes.csv` never defines has no signature to compute —
    # every one of its variants would read as reference, which is a claim rather than a computation.
    # That case already has its own warning; here it is simply skipped.
    by_signature: dict[tuple, list[Any]] = {}
    for row in diplotypes:
        pair = (row.haplotype_a, row.haplotype_b)
        if not all(name in definitions for name in pair):
            continue
        by_signature.setdefault((row.gene, _unphased_signature(pair, definitions, variants)), []).append(row)

    warnings: list[str] = []
    undistinguished: dict[str, list[str]] = {}
    unphased: dict[str, list[str]] = {}
    for (gene, _signature), rows in by_signature.items():
        # **Distinct haplotype PAIRS, not distinct rows** — the bug the first draft shipped, caught by
        # compiling the real CYP2C19 example. One pair legitimately carries many rows: the dedup key
        # is (gene, a, b, trait_efo_id, drug, clinical_context), so `*10/*10` has a row per drug and
        # per clinical context, all with the same signature by construction and different conclusions
        # by design. Flagging those reported 595 phase ambiguities in a module that has none, and the
        # message named the same pair twice, which is what gave it away.
        pairs = sorted({(row.haplotype_a, row.haplotype_b) for row in rows})
        if len(pairs) < 2:
            continue
        # Two *different* pairs that state the same thing are harmless — a consumer reporting either
        # is right. Only a disagreement is a finding.
        if len({(row.conclusion, row.phenotype, row.direction, row.clin_sig) for row in rows}) < 2:
            continue

        # **Phase does not always resolve it, and saying so was overclaiming.** Caught by compiling a
        # real 16,290-row CYP2D6 draft: `*10/*8`, `*100/*8`, `*101/*8` and `*147/*8` collide because
        # `*10`, `*100`, `*101` and `*147` carry *identical defining-variant sets* (rs1058164 G,
        # rs1065852 A, rs1135840 G — CPIC's core definitions do not separate these suballeles). Those
        # pairs are indistinguishable **at all**, phased or not, so telling an author "a phased
        # consumer resolves it" would send them to buy phasing that cannot help. Grouping the pairs by
        # their *phase-preserving* signature separates the two cases exactly: same multiset of
        # haplotype definitions → nothing distinguishes them; different → phase does.
        by_definition: dict[tuple, list[tuple[str, str]]] = {}
        for pair in pairs:
            key = tuple(sorted(tuple(sorted(definitions[name].items())) for name in pair))
            by_definition.setdefault(key, []).append(pair)

        for identical in by_definition.values():
            if len(identical) > 1:
                undistinguished.setdefault(gene, []).append(", ".join(f"{a}/{b}" for a, b in identical))
        distinct = [same[0] for same in by_definition.values()]
        if len(distinct) > 1:
            unphased.setdefault(gene, []).append(", ".join(f"{a}/{b}" for a, b in sorted(distinct)))

    # One warning per gene per class, with examples and a count — the aggregation rule CPIC taught and
    # this check had to relearn: the real CYP2D6 draft produces 378 identically-defined groups and 20
    # phase-ambiguous ones, and 398 lines bury every other finding a compile emits. Deterministic
    # order (first-occurrence per gene, P7), and the count is always stated so nothing is silently
    # capped.
    for gene, groups in undistinguished.items():
        warnings.append(
            CodedWarning(
                "diplotype_definitions_identical",
                f"{gene}: {len(groups)} group(s) of diplotype rows name haplotypes this module defines "
                f"identically, so nothing in it can tell them apart — phase does not help. A consumer's "
                f"caller may still emit each name and the rows disagree, so at most one can be right: "
                f"either the defining variants are incomplete or the rows describe one allele under "
                f"several names. {_examples(groups)}",
            )
        )
    for gene, groups in unphased.items():
        warnings.append(
            CodedWarning(
                "diplotype_phase_ambiguous",
                f"{gene}: {len(groups)} group(s) of diplotype rows are indistinguishable without phase — "
                f"same unphased genotype, different conclusions. A consumer with unphased calls must "
                f"withhold rather than pick one; a phased consumer resolves it. {_examples(groups)}",
            )
        )
    return warnings


def _examples(groups: list[str], limit: int = 3) -> str:
    """`e.g. A, B, C (+N more)` — the shape `pgx_draft` already uses for a repeated finding."""
    shown = "; ".join(groups[:limit])
    extra = len(groups) - limit
    return f"e.g. {shown}" + (f" (+{extra} more)" if extra > 0 else "")


def _cross_validate_studies(
    studies: list[StudyRow], variants: list[VariantRow]
) -> tuple[list[str], list[str]]:
    """Validate study rows against the variants. Returns (errors, warnings).

    A study matches a variant on **any shared identifier** — same rsid or same `chrom:start:ref` —
    not on frozen-key equality. Keying strictly on `variant_key` would false-orphan a study that
    references a variant by a different (but co-identifying) handle than the one the variant froze its
    key to (e.g. a coord-keyed variant referenced by rsid).

    **A row that names no variant is not an orphan** (RM47): since 0.6 a citation row may ground the
    module or a binning bound rather than a locus, and a row referencing nothing cannot reference
    something missing. Its dedup key is `(None, pmid)`, so two subject-less rows citing one paper are
    still a duplicate — deliberately: they are the same claim written twice, and the whole point of
    the relaxation is that one such row is enough.

    **Since RM140 a stated `statistical_test` splits that key for this check** (S75). One paper often
    reports several analyses of one association with different statistics, and those rows are not one
    claim written twice. Only *both stated and different* suppresses: an absent analysis is unknown,
    and unknown cannot establish distinctness."""
    warnings: list[str] = []
    variant_rsids = {v.rsid for v in variants if v.rsid is not None}
    variant_coords = {
        derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None
    }
    orphans: list[str] = []
    for row in studies:
        if row.variant_key is None:
            continue
        by_rsid = row.rsid is not None and row.rsid in variant_rsids
        by_coord = (
            row.chrom is not None
            and derive_variant_key(None, row.chrom, row.start, row.ref) in variant_coords
        )
        if not by_rsid and not by_coord:
            orphans.append(row.variant_key)
    if orphans:
        warnings.append(
            CodedWarning(
                "study_variant_orphan",
                f"Studies reference variants not in variants.csv: {sorted(set(orphans))}",
            )
        )
    # `(variant_key, pmid)` is the dedup key, and since RM140 a *stated* `statistical_test` splits it
    # for this check only. One paper routinely reports several analyses of one association — an
    # allelic Fisher's exact and a univariate logistic regression of the same variant, with different
    # p-values — and those are two claims, not one claim written twice, which is what the docstring
    # above says a duplicate is. `StudyRow._KEY_FIELDS` is deliberately NOT widened: it drives
    # `hints.key_fields` and the `key.columns` an authoring surface publishes, and re-keying a shipped
    # authored table is a major-only change under P3. This check restates the pair rather than reading
    # `_KEY_FIELDS`, so the divergence is contained here and is the whole of it.
    #
    # **Both stated and different is the only suppressing case, because `None` is not "different".**
    # An unstated analysis is *unknown*, and unknown against a stated one cannot establish that the two
    # rows describe separate work — Kleene, not `a != b`, which would suppress on every absent cell and
    # silently retire the check for every module written before the column existed. So a row whose
    # analysis is unrecorded, or that repeats an analysis already stated for the same key, warns exactly
    # as it did; the message is unchanged for every case that still reports.
    stated: dict[tuple[str | None, str], set[str]] = {}
    unstated: dict[tuple[str | None, str], int] = {}
    for row in studies:
        key = (row.variant_key, row.pmid)
        test = row.statistical_test.strip() if row.statistical_test else None
        if key not in stated:
            stated[key] = set()
            unstated[key] = 0
        else:
            names_a_new_analysis = test is not None and test not in stated[key] and unstated[key] == 0
            if not names_a_new_analysis:
                warnings.append(
                    CodedWarning(
                        "duplicate_study_citation",
                        f"Duplicate (variant, pmid): ({row.variant_key}, {row.pmid})",
                    )
                )
        if test is None:
            unstated[key] += 1
        else:
            stated[key].add(test)
    return [], warnings


def _validate_table_kind(
    csv_name: str, model: type[BaseModel], rows: list[Any]
) -> tuple[list[str], list[str]]:
    """Table-level coherence for one table, after per-row validation has passed.

    Run over the 0.4 authored kinds and, since RM107, over the injected fact tables as well — the
    split was never a rule about which tables deserve the checks, only about which loop happened to
    call this. A model with no entry in either registry gets `([], [])`, so widening the call site
    tightens nothing that was not already keyed.

    Returns (errors, warnings). Two families of check:

    - **Binning tables** (`MeasureBinRow` subclasses) run `validate_bins` — overlapping resolved bins
      are an **error** (a measurement would select two phenotypes), interior coverage gaps a
      **warning**. Plus: at most one `unresolved` sentinel per key group (a consumer selects one when
      the measurement is absent, so two is ambiguous) — an error.
    - **All keyed kinds** get duplicate-row detection via `_TABLE_DUPE_KEYS` — an error, mirroring the
      SNP core's duplicate-(variant, genotype) rule.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if issubclass(model, MeasureBinRow):
        # The `try` covers the CALL and nothing else. `validate_bins` raises `ValueError` for an
        # overlapping resolved bin, and so does `restate` for a finding that arrived with no code —
        # so a wider block would file a missing warning code as a bin-overlap refusal on the table,
        # which is both a false diagnosis and a silencing of the one failure the codes exist to make
        # loud. Two `ValueError`s, one meaning each, kept apart by scope rather than by inspection.
        try:
            bin_findings = validate_bins(rows)
        except ValueError as exc:
            errors.append(f"{csv_name}: {exc}")
            bin_findings = []
        # `restate`, not an f-string: the prefix would otherwise strip the code `validate_bins` named
        # — the three tiling/coverage findings are not one kind.
        warnings.extend(restate(w, f"{csv_name}: {w}") for w in bin_findings)
        sentinels: dict[tuple, int] = defaultdict(int)
        for r in rows:
            if r.unresolved:
                group = tuple(getattr(r, f, None) for f in r._KEY_FIELDS) + (r.trait_efo_id,)
                sentinels[group] += 1
        for group, count in sentinels.items():
            if count > 1:
                errors.append(
                    f"{csv_name}: {count} unresolved sentinel rows for key "
                    f"{format_group_key(group)} — a consumer selects one when a measurement is "
                    f"absent, so at most one is allowed"
                )

    keyfn = _TABLE_DUPE_KEYS.get(model)
    if keyfn is not None:
        seen: set[tuple] = set()
        for r in rows:
            key = keyfn(r)
            if key in seen:
                errors.append(f"{csv_name}: duplicate row for key {key}")
            seen.add(key)

    return errors, warnings


# ── Public API ─────────────────────────────────────────────────────────────────


# Every filename the spec directory has a meaning for. Derived from the table registries rather than
# listed, so a new table kind cannot be missed here. Used only to recognise a *near miss* — a spec
# directory may carry anything else it likes (see `_check_misspelled_tables`).
_KNOWN_SPEC_FILES: frozenset[str] = frozenset(
    {"module_spec.yaml", "variants.csv", "studies.csv", _PROVENANCE_FILE, VERIFICATION_JSON}
    | set(_TABLE_KIND_CSVS)
    # The overlay joins by its ONE legal name and deliberately not through `sidecar_spellings`: it is
    # authored, so it has one place (the spec root) like `variants.csv`, and being in the authored set
    # is what makes a stray `derived/overrides.csv` reported as a misplaced table rather than
    # tolerated — the rows in it would otherwise be read from nowhere.
    | {OVERRIDES_CSV}
    # Every accepted spelling, not just the one the registries name — a sidecar the compiler happily
    # reads under an alias must not also be reported as a near-miss stray file in the same run (RM51).
    | {name for csv, _, _ in _FACT_TABLES for name in sidecar_spellings(csv)}
    | set(sidecar_spellings("resolution.csv"))
)


#: Extensions the near-miss guard inspects **at the spec root**. `.json` joined `.csv` when
#: `verification.json` landed (RM45); `derived/` deliberately stays `.csv`-only, and the reason the two
#: differ is argued at the loop in `_check_misspelled_tables`. The guard's precision comes from the
#: near-miss cutoff rather than from the extension, which is what lets it warn about a typo without
#: warning about the curation notes beside it.
_ROOT_NEAR_MISS_SUFFIXES: frozenset[str] = frozenset({".csv", ".json"})


def _check_misspelled_tables(spec_dir: Path) -> list[str]:
    """Warn when an unknown `.csv` is one small edit from a table name the compiler knows.

    **Unknown files are ignored on purpose and that is a contract** (S16): a module may carry curation
    notes or a publisher's receipt, neither of which is in `artifact.files` and so neither of which
    moves the digest. The hazard is the narrow case where "ignored" is the wrong answer — a *mistyped
    table name*. `varaints.csv` is silently not a table, so the author's rows are dropped and the
    compile is green, which is the silent-success shape this codebase treats as the worst kind of
    mistake. Probed on a real spec: three extra files, including that typo, produced no message and an
    unchanged digest.

    A `README.md` was the headline example of a tolerated file until S25 gave it a manifest field, and
    it is now *collected* — copied into the module dir and hashed into `manifest.readme`. That changes
    nothing here (the check reads only `.csv` names) but the two claims are no longer the same claim:
    a readme is read and hashed, and still moves no digest, because `manifest.readme` sits outside
    `artifact.files` exactly as `logo` does.

    Deliberately keyed on **near miss** rather than on "unknown csv": warning about every unrecognised
    file would fire on the legitimate sidecars the contract exists to permit, so the check has to be
    high-precision or it undoes the tolerance. `difflib` at a 0.8 cutoff catches a transposition, a
    doubled or dropped letter, and a singular/plural slip, and stays quiet on an unrelated name.

    **`derived/` is scanned too, and it takes TWO tests rather than one (RM49).** Tolerating a second
    input location without teaching this check about it would put a typo'd `derived/varaints.csv`
    exactly where the guard cannot see it — re-opening the hole S16 closed, as the price of a
    convenience. That is also the argument against "search any subdirectory": one fixed name is the
    only version where the guard can follow.

    What is *legal* there is the derived files alone, but that smaller set is the wrong thing to
    fuzzy-match against, and matching against it was measured to catch neither case: at a 0.8 cutoff
    `variants.csv`, `studies.csv` and `repeat_alleles.csv` are **no** near miss of any sidecar name,
    and neither is `varaints.csv` — the very file this check exists for. So the two mistakes are
    separated. An **authored table name under `derived/` is an exact match against the wrong name
    set**, which is a sharper test than any fuzzy one and is reported as a misplaced table: those rows
    are read from nowhere, and a module that keeps another table at the root compiles green without
    them. Anything else there is fuzzy-matched against the **full** known set, so a typo'd authored
    name lands too. The mirror case stays silent by construction — a derived sidecar at the spec root
    is a legal place for it, so the root's own legal set already accepts it."""
    if not spec_dir.is_dir():
        return []
    derived_names = frozenset(name for csv in _DERIVED_FILES for name in sidecar_spellings(csv))
    # The authored DSL: one legal name in one legal place, so any of these under `derived/` is
    # misplaced. Derived by subtraction rather than listed — a new table kind joins it for free.
    authored_names = _KNOWN_SPEC_FILES - derived_names
    warnings: list[str] = []
    # The suffix set is **per directory**, and the asymmetry is the point rather than an oversight.
    #
    # Under `derived/`, both branches below are about a **table** whose rows are being dropped, so both
    # stay behind the `.csv` filter. `derived/provenance.json` and `derived/module_spec.yaml` are
    # therefore ordinary tolerated strays: neither has rows to lose, a misplaced `module_spec.yaml`
    # cannot hide (the root one is required and its absence is an error), and `provenance.json` is
    # exactly the machine-written document a registry splitting a tree might reasonably put there.
    # Widening *that* branch would actively misreport it — `provenance.json` is in the authored set by
    # subtraction, so it would be named as an authored table in the wrong place, which it is not.
    #
    # At the **root** the near-miss branch reads `.json` too (RM45). What is lost there is not rows but
    # a whole document: a typo'd `verifcation.json` silently is not an attestation, so the module reads
    # as *nothing verified* while its author believes the checks are recorded — the same silent-success
    # shape, one file kind over. It retroactively covers `provenance.json`, which had been in the
    # known-name set since 0.4 with no suffix that could reach it. Neither `published.json` nor any
    # other registry receipt is within one edit of a known name, which is the property that keeps the
    # tolerance beside it intact (measured, not assumed).
    scans = (
        (spec_dir, _KNOWN_SPEC_FILES, _ROOT_NEAR_MISS_SUFFIXES),
        (spec_dir / DERIVED_SUBDIR, derived_names, frozenset({".csv"})),
    )
    for directory, legal, suffixes in scans:
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.name in legal or path.suffix not in suffixes:
                continue
            shown = path.relative_to(spec_dir)
            if path.name in authored_names:
                warnings.append(
                    CodedWarning(
                        "table_file_misplaced",
                        f"{shown} is an authored table sitting in {DERIVED_SUBDIR}/, which holds only the "
                        f"machine-written sidecars — every row in it is being silently ignored. Move it to "
                        f"the spec root. Only resolution.csv and the fact tables have a second legal home.",
                    )
                )
                continue
            close = difflib.get_close_matches(path.name, sorted(_KNOWN_SPEC_FILES), n=1, cutoff=0.8)
            if close:
                warnings.append(
                    CodedWarning(
                        "table_file_near_miss",
                        f"{shown} is not a table this compiler reads, and it is one small edit from "
                        f"{close[0]!r} — if that is a typo, every row in it is being silently ignored. "
                        f"Unknown files are otherwise tolerated (curation notes or a publisher's receipt "
                        f"are fine): nothing outside the known table set reaches artifact.digest.",
                    )
                )
    return warnings
