"""Commands for the host's local FASTA reference."""

from pathlib import Path

import typer

from just_dna_enricher.fasta import FastaConfigurationError, write_fasta_index

fasta_app = typer.Typer(help="Prepare a local FASTA reference.", no_args_is_help=True)


@fasta_app.command("index")
def fasta_index(path: Path) -> None:
    """Write the five-column .fai beside an uncompressed FASTA."""
    try:
        index = write_fasta_index(path)
        with index.open("rb") as handle:
            count = sum(1 for _ in handle)
    except (FastaConfigurationError, OSError) as exc:
        raise typer.BadParameter(str(exc), param_hint="PATH") from exc
    typer.echo(f"{index} ({count} {'contig' if count == 1 else 'contigs'})")
