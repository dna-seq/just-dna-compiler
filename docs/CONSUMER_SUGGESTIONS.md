# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

## S143 — `gwas.py` asks the GWAS Catalog v2 for a page of 1000, which it refuses with 400, so the GWAS pass fails on every module

*From just-module-creator (the liaison, on the tester's report, its F146), 2026-11-10.*

What we ran: the GWAS-effects pass (`enrich_gwas_effects`, use `non_commercial`) on a copy of a one-variant
module (rs1421085), on our branch that installs enricher 0.8.3.

What we expected: the associations for rs1421085, of which the Catalog holds 223.

What happened: the pass returns no rows and the warning `GWAS Catalog returned 400 for
https://www.ebi.ac.uk/gwas/rest/api/v2/associations?rs_id=rs1421085&size=1000`. The page size is the cause:
`just_dna_enricher/gwas.py` sets `_PAGE_SIZE = 1000` (line 119, on the `v0.8.3` tag and on `main`) and sends it as
`size` in the first request of the paging loop. The same request by hand:

| `size` | HTTP |
|---|---|
| 100, 200, 500 | 200 (`size=500` returns all 223 on one page) |
| 501, 999, 1000 | 400 `Bad Request` |

Measured by the tester the same evening, and `1000` → 400, `500` → 200 again here at 22:56 UTC. So every rsID
fails, not only large ones: the first page is refused before any paging. The pass reports it honestly as a
failure (unchecked, not empty), which is the S20 shape working as meant.

What we did meanwhile: nothing; it is not ours to work around. Our released plugin installs 0.7.x, which reads
the Catalog's v1 API and is unaffected; only our 0.8 adoption branch meets it.

Candidate fix: `_PAGE_SIZE = 500`, the Catalog's ceiling as measured; the loop already follows `next` links, so
a variant with more than 500 associations still comes back whole. A test asserting the constant is at most the
documented maximum would catch the next change on their side; a recorded-response test cannot, since the 400
only comes from the live service. Against it: 500 is measured, not documented in what we read, so the Catalog
could lower it again; a pass that retries once with a smaller page on a 400 would survive that, at the cost of
one more request per failure.

**Status — filed as [RM428](ROADMAP.md#rm428--the-gwas-pass-asks-the-catalog-v2-for-a-page-of-1000-which-it-now-refuses-with-400-so-the-pass-fills-nothing-on-any-module): ask 1 a patch; the pm sizes asks 2 and 3.** Confirmed. Here at 22:58 UTC,
`size=500` answers 200, and 501 and 1000 answer 400, whose body is a bare `Bad Request` and does not name the limit.
The Catalog moved, not the code. RM354 measured `size=1000` returning all 386 associations of rs4149056 on
2026-11-04, so the ceiling dropped on their side in the six days after. The module docstring assumed a server that
caps a large page, and this one refuses it. Ask 1 is your `_PAGE_SIZE = 500`. On the guard, your reason against a
unit test holds: with no documented maximum, it would pin a number the server decides. RM428 offers the pm an opt-in
live test (`@pytest.mark.network`) that asks with the real constant, the only test that can see the 400. Your
retry-with-a-smaller-page sits beside the other way to survive the next drop, v2's default page of 20, which costs
about twenty requests where one would do for a variant like rs4149056. Your 0.7.x release is unaffected, as you say.
Your 0.8 branch waits for the patch after 0.8.3.

<!-- triaged: RM428 filed (patch page size; guard and fallback with the pm) · sha e9c0005d744e -->
