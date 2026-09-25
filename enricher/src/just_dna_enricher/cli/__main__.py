"""`python -m just_dna_enricher.cli` — the module form of the `just-dna-enricher` console script."""

from just_dna_enricher.cli import app

# **Last line of the file, and that is the whole of this fix (RM100).** It used to sit at line 1688,
# above the `hint` sub-app, `draft-clinpgx`, `draft-panel` and `clinvar citations` -- so
# `python -m just_dna_enricher.cli` ran `app()` before those registrations executed and exposed 23 of
# the 26 top-level commands. Harmless through the `[project.scripts]` entry point, which imports the
# module fully and then calls `app()`, and wrong for anyone invoking the module directly.
if __name__ == "__main__":
    app()
