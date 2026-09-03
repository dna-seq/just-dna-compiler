# `civic_api_slice` — recorded CIViC GraphQL responses (RM160)

Three real `evidenceItems(variantId:, status: ALL)` responses, captured 2026-09-03 from
`https://civicdb.org/api/graphql` with the query `civic_api._EVIDENCE_QUERY` sends. Verbatim bodies,
pretty-printed and key-sorted so a diff is readable; nothing in them is edited.

They are here because the suite must not fetch (`JUST_DNA_NETWORK_TESTS=1` is opt-in), and because
each one carries a shape the lane has to get right. Every expected value in the tests is derived from
these files at runtime — no count is copied out of them into a test.

| file | variant | why this one |
| --- | --- | --- |
| `evidence_1955.json` | 1955 `VHL P71fs (c.211insT)` | The motivating record. Two items, one `ACCEPTED` and one `SUBMITTED`, and the submitted one (EID 9969, PMID 12202531, free full text) is the only reachable evidence for the numbering convention its identity turns on. It exists here and in no file the builder reads. |
| `evidence_844.json` | 844 `VHL Exon 1 Deletion` | The volume case, and the many-items-one-paper case: five evidence items cite PMID 17661816, which `studies.csv` holds as **one** row keyed `(variant_key, pmid)`. Also the fixture the paging test splits, because it is the only one long enough to split. |
| `evidence_1939.json` | 1939 `VHL Exon 3 Deletion` | The only variant measured to carry a `REJECTED` item, and the only one where one paper (PMID 28256701) is cited by both an accepted and a rejected item — the case that decides whether a status is stateable at all. |
