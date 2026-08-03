---
name: write-module
description: >-
  Author a just-dna annotation module (format 0.5) end to end — choose the table kinds, draft from a
  source, curate what only a human can decide, enrich, cross-check, compile, sign. Use when creating
  or extending a module spec directory (module_spec.yaml + CSVs), when picking which table kind a
  finding belongs in, or when a validate/enrich/compile step reports something you do not recognise.
  Triggers: "write a module", "author a module", "add a gene/panel/variant", "draft from ClinVar",
  "draft from CPIC", "heteroplasmy", "star alleles", "diplotypes", "module_spec.yaml", "variants.csv",
  "why does my module not compile".
---

# Writing a just-dna module

The workflow lives in the repo docs, not here — one copy, versioned with the code it describes.

**Read [`docs/AUTHORING.md`](../../../docs/AUTHORING.md) now, in full.** It is ~170 lines and it carries
the command order, which matters: there is one place where deviating from it deadlocks (a drafted
placeholder blocks every loader, `enrich` included, so you curate *before* enriching).

Then, as the task needs:

| Read | When |
|---|---|
| [`docs/AUTHORING_TABLES.md`](../../../docs/AUTHORING_TABLES.md) | Choosing which table kind a finding belongs in, or which axes must go in a key. |
| [`docs/AUTHORING_SYMPTOMS.md`](../../../docs/AUTHORING_SYMPTOMS.md) | Anything reports a message you do not recognise. Match on the quoted phrase. |
| [`docs/RM_TOC.md`](../../../docs/RM_TOC.md) | Checking whether a limitation you hit is already tracked (RM31–RM35 must not be worked around in data). |
| [`docs/CONSTITUTION.md`](../../../docs/CONSTITUTION.md) | Only if you are changing the **schema** rather than authoring against it. Read it in full yourself; never delegate it. |

Do not re-derive the flow from `SCHEMAS.md` / `COMPILER.md` / `ENRICHER.md` — those are the package
references, and the authoring order is not obvious from them. That is why this guide exists.
