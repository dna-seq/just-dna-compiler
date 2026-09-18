"""The sentences the two resolution twins speak, in one place (RM244).

**Why this module exists.** `just_dna_compiler.resolution` resolves against an injected
`resolution.csv` and `just_dna_enricher.resolver` resolves against an injected Ensembl reference, and
the two deliberately share their `VALID_WARNING_CODES` members: the finding is the same finding and the
remedy is the same remedy, which the enricher's own comment says in as many words. What they did **not**
share was the words. Nine codes were emitted by both tiers and **seven pairs were a different sentence**
— `rsid_unresolved` read *"not found in resolution table, position remains unset"* in one and *"not in
the injected Ensembl snapshot"* in the other. A warning's text is an API a consumer greps
(`@warning-text-is-api`), so one code with two sentences is one code a consumer can only half-match.

**It lives in the compiler, not in the format tier**, because the enricher already imports
`just_dna_compiler.resolution.genotype_fits` — that module is already the shared resolution vocabulary
across the `enricher → compiler → format` chain — and because when the enricher's deprecated
`ensembl_cache` route is removed at 1.0 the compiler is the sole remaining caller. Nothing here imports
anything: they are string builders, so no tier gains a dependency and `just_dna_format` is untouched.

**A builder returns `str`, never a `CodedWarning`.** Each tier wraps the text at its own site, so the
literal `CodedWarning("<code>", …)` call stays where the code is emitted — which is what
`schema/tests/test_feature_corpus.py` aligns every `@code:` scenario against, and what keeps the
`(code, tier)` grounding equality readable rather than chased through an indirection.

**`None` means this caller cannot establish the clause, and the clause is then omitted.** That is the
house tri-state applied to a sentence rather than to a column: a tier that does not know something
withholds it instead of guessing or inheriting the other tier's guess. Three of the omissions are
recorded decisions rather than conveniences, and each is named at the builder that carries it:

* **S61** — the enricher's snapshot leg may not say *position remains unset*, because a live leg it
  neither runs nor knows about may still answer. At that point the consequence is genuinely unknown.
* **S33** — the compiler accumulates one expansion sentence per rsID with the real row total; the
  enricher's per-row copy was deliberately left alone because it is on the deprecated `ensembl_cache`
  route, removed at 1.0, and porting the accumulator into a function that is going away would duplicate
  it rather than share it.
* The enricher cannot name which *tables* a cross-build skip left unjoined, because it resolves
  variants rather than filling positional tables.
"""


def unresolved_rsid(subject: str, *, searched: str, consequence: str | None = None) -> str:
    """An rsID the consulted table or snapshot has no usable locus for.

    `consequence` is the **S61 withhold**: the compiler knows the position stays unset because its
    injected table is the only thing that was going to place the row, and the enricher's snapshot leg
    does not, because `lookup_variant`'s live leg runs after it. So the compiler passes the clause and
    the enricher passes `None`, and the sentence that reaches a consumer is shorter rather than wrong.
    """
    tail = f", {consequence}" if consequence else ""
    return f"{subject}: not in {searched}{tail}"


def no_hosting_locus(subject: str, *, loci: int, genotype: str | None) -> str:
    """Every locus the identity reaches contradicts the authored genotype, so nothing is filled.

    The one pair of the nine that already agreed byte for byte, written separately in two tiers. It is
    shared for the same reason as the rest: agreeing today is not a property either sentence has.
    """
    return (
        f"{subject}: none of its {loci} loci can host the authored genotype "
        f"{genotype}; position remains unset"
    )


def locus_cannot_host(
    subject: str,
    *,
    locus: str,
    ref: str | None,
    alts: str | None,
    genotype: str | None,
    instead: str | None = None,
    caveat: str = "",
) -> str:
    """One locus of a multi-locus identity cannot carry the call, so that locus leaves the expansion.

    `instead` is what the compiler says the dropped row is *not* — a row asserting an allele the locus
    does not have. It is a clause about the artifact, and the enricher writes no artifact, so the
    enricher withholds it rather than borrowing a claim it is not in a position to make.
    """
    tail = f" {instead}" if instead else ""
    return (
        f"{subject} maps to {locus} {ref}>{alts}, which cannot host the authored "
        f"genotype {genotype} — that locus is dropped from the expansion{tail}.{caveat}"
    )


def skipped_cross_build(
    *,
    what: str,
    genome_build: str,
    not_joined_onto: str | None = None,
    kept: str | None = None,
) -> str:
    """The module is on an assembly the GRCh38-bound resolver will not re-resolve against.

    Three callers and one sentence: the compiler's resolution fill, the compiler's positional-table
    fill, and the enricher's Ensembl leg. `not_joined_onto` names the tables the positional fill left
    alone, which is a fact only that caller has — the other two resolve variants and join no table.
    """
    text = (
        f"{what} skipped: compiler is GRCh38-bound, module genome_build is "
        f"{genome_build!r} — positions are not re-resolved cross-build (RM15)."
    )
    if not_joined_onto:
        text += f" The injected resolution table is not joined onto {not_joined_onto}."
    if kept:
        text += f" {kept}"
    return text


def resolution_not_injected(*, missing: str, remedy: str | None = None) -> str:
    """Nothing was injected to resolve against — nobody-asked rather than asked-and-absent.

    `missing` names what this tier looked for, because the two look for different things: the compiler
    for a `resolution.csv` or an `ensembl_cache`, the enricher for a reference cache on any of its
    searched paths. `remedy` is `None` where the caller is reporting an exception it cannot turn into
    an instruction; the reason travels in `missing` instead.
    """
    text = f"{missing}; variants lacking a genomic position are left unresolved."
    if remedy:
        text += f" {remedy}"
    return text


def without_resolution_label(*, subject: str, searched: str, reassurance: bool = True) -> str:
    """A coordinate-authored row the consulted source names no rsID for.

    Not an error in either tier, and the half that says so is what the enricher's per-position copy was
    missing: a coordinate is already a complete identity. `subject` carries the grain — the compiler
    aggregates over rows and the enricher speaks per position — because the grain is a real difference
    and a builder that hid it would make one of the two lie about how many rows it is describing.
    """
    text = f"{subject}: no rsid found in {searched}"
    if reassurance:
        text += ". Not an error — a coordinate is a complete identity and an rsID is a label on top of it"
    return text


def expanded_to_multiple_loci(
    *,
    subject: str,
    loci: int,
    rows: int,
    where: str,
    from_clause: str = "",
    keying: str,
    reader_note: str,
) -> str:
    """An identity that names more than one place, expanded to one row per locus.

    **S33 is why this is a skeleton with slots rather than one sentence.** The compiler accumulates per
    rsID over every authored row and reports the real row total; the enricher's copy is per authored row
    and is deliberately left that way, because it is on the deprecated `ensembl_cache` route, removed at
    1.0, and the modules reaching it report `expanded_keys`/`expanded_rows` as `None` rather than as a
    count. Porting the accumulator into a function that is going away would duplicate it, not share it.

    `from_clause` earns its place only when one rsID carried more than one authored genotype: on the
    ordinary expansion the two numbers are equal and the clause is noise. `reader_note` is the half a
    reader gets wrong — only one member of an expansion can match a given genotype — and the two tiers
    say as much of it as they can stand behind.

    The compiler's **pseudoautosomal** branch is deliberately not routed through here: a PAR expansion
    and a paralogous one produce the same row count for opposite reasons, and reporting both with the
    same skeleton is what once told a SHOX author to count ten findings as twenty. That is a different
    finding wearing the same code, and it says so in its own words.
    """
    return (
        f"{subject} maps to {loci} loci{where}; expanded to {rows} rows{from_clause}, {keying}. {reader_note}"
    )


def coordinate_disagrees(*, subject: str, authored: str, reported: str, reading: str | None = None) -> str:
    """An authored rsID↔coordinate pair the consulted source does not pair.

    `reading` is the hedge the enricher carries and the compiler does not: a disagreement may be a dbSNP
    merge or a build difference rather than an error, and the enricher is reporting while the compiler
    is deciding whether `strict` can build on it. Neither tier writes the opposite value
    (`@refutation-withholds`) — the authored value is kept either way.
    """
    hedge = f" — {reading}" if reading else ""
    return f"{subject} authored as {authored}, but {reported} (reference disagreement{hedge})."


def ambiguous_pick(
    *,
    subject: str,
    observed: str,
    candidates: str | None = None,
    resolved_to: str | None = None,
    remedy: str | None = None,
) -> str:
    """Several ids at one place, and the pick is deterministic rather than right.

    The `ORDER BY` and the sort fix which one wins, so the answer is stable; stable is not the same as
    established, which is why both tiers say the pick is a pick
    (`@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`). That clause is the whole
    of what they share.

    **`observed` is a slot because the two tiers are describing different events.** The compiler is
    reading a label the enricher already wrote — `resolution.csv` says `ambiguous` — so it reports that
    the *rsid resolved as AMBIGUOUS*. The enricher is at the moment of choosing: it built a reverse map
    and a ref-less key reached several dbSNP ids, and nothing has resolved anything yet. Folding the two
    into one sentence would have the enricher announce a table state that does not exist. `remedy` splits
    the same way — the author disambiguates by giving `ref` where the enricher speaks, and by editing
    `resolution.csv` where the compiler does.
    """
    among = f" among {candidates}" if candidates else ""
    to = f"; resolved to {resolved_to} deterministically" if resolved_to else ""
    tail = f" {remedy}" if remedy else ""
    return (
        f"{subject}: {observed}{among}{to} — the deterministic pick is carried, "
        f"and it is a pick, not a finding.{tail}"
    )
